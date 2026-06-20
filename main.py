# -*- coding: utf-8 -*-
"""
QQ 音乐下载辅助工具 - CLI 版本
集成解密、格式转换、歌词清理等功能
"""

import argparse
import sys
import os
import logging
import hashlib
import shutil
import tempfile
import subprocess
import time

try:
    import frida
except ImportError:
    frida = None

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, COMM, APIC
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


# ==================== 解密功能模块 ====================

def list_download_songs(directory=None, extensions=None):
    """
    列出 QQ 音乐下载目录下的歌曲
    
    Args:
        directory: 指定目录，如果为 None 则使用默认下载目录
        extensions: 文件扩展名列表，如果为 None 则使用默认扩展名
    """
    # 如果没有指定目录，使用默认下载目录
    if directory is None:
        download_dir = os.path.join(os.path.expanduser("~"), "Music", "VipSongsDownload")
        # 如果默认目录不存在，尝试其他常见路径
        if not os.path.exists(download_dir):
            # 可以尝试自定义路径，如: os.path.join("E:", "music", "VipSongsDownload")
            pass
    else:
        download_dir = directory
    
    if not os.path.exists(download_dir):
        logging.error(f"目录不存在：{download_dir}")
        return
    
    if not os.path.isdir(download_dir):
        logging.error(f"路径不是目录：{download_dir}")
        return
    
    # 默认扩展名
    if extensions is None:
        exts = {".mflac", ".mgg", ".ogg", ".flac", ".mp3", ".m4a"}
    else:
        # 将用户输入的扩展名转换为集合，确保以 . 开头
        exts = set()
        for ext in extensions:
            ext = ext.lower().strip()
            if not ext.startswith('.'):
                ext = '.' + ext
            exts.add(ext)
    
    logging.info(f"扫描目录：{download_dir}")
    logging.info(f"文件类型：{', '.join(sorted(exts))}")
    count = 0
    for root, _, files in os.walk(download_dir):
        for file in files:
            if os.path.splitext(file)[1].lower() in exts:
                count += 1
                full_path = os.path.join(root, file)
                rel = os.path.relpath(full_path, download_dir)
                print(f"{count:4d}. {rel}")
    logging.info(f"共找到 {count} 个文件")


def run_decrypt(input_dir, output_dir, output_format=None, replace_mode=False):
    """
    执行解密操作
    
    Args:
        input_dir: 输入目录（包含加密文件）
        output_dir: 输出目录
        output_format: 输出格式 (mp3, flac, ogg, wav, m4a)，None 则使用默认格式
        replace_mode: 是否为原地替换模式，如果是则在成功后删除源文件
    """
    if frida is None:
        logging.error("未安装 frida 模块，请先运行: pip install frida")
        return
    
    if not os.path.exists(input_dir):
        logging.error(f"输入目录不存在: {input_dir}")
        return

    input_dir = os.path.abspath(input_dir)
    # 只有当 output_dir 不为 None 时才转换为绝对路径
    if output_dir is not None:
        output_dir = os.path.abspath(output_dir)

    # 如果指定了输出格式，检查 ffmpeg
    if output_format and not check_ffmpeg():
        logging.error("需要 ffmpeg 进行格式转换，但未检测到 ffmpeg")
        logging.info("下载地址: https://ffmpeg.org/download.html")
        return

    logging.info(f"解密模式: 输入={input_dir}, 输出={'源文件所在目录' if output_dir is None else output_dir}")
    if output_format:
        logging.info(f"目标格式: {output_format.upper()}")
    
    try:
        session = frida.attach("QQMusic.exe")
    except frida.ProcessNotFoundError:
        logging.error("未找到 QQMusic.exe 进程，请先启动 QQ 音乐")
        return

    script_loaded = False
    script_error = None
    
    try:
        with open("hook_qq_music.js", "r", encoding="utf-8") as f:
            script = session.create_script(f.read())
        
        # 添加消息监听器
        def on_message(message, data):
            nonlocal script_error
            if message['type'] == 'log':
                logging.info(f"[Frida] {message['payload']}")
            elif message['type'] == 'error':
                error_msg = message.get('stack', message.get('description', 'Unknown'))
                logging.error(f"[Frida Error] {error_msg}")
                script_error = error_msg
        
        script.on('message', on_message)
        script.load()
        
        # 等待脚本初始化完成
        for i in range(10):  # 最多等待 2 秒
            time.sleep(0.2)
            if script_error:
                logging.error("脚本初始化失败，退出")
                return
            # 检查 exports 是否可用
            try:
                if hasattr(script, 'exports_sync') and hasattr(script.exports_sync, 'decrypt'):
                    script_loaded = True
                    logging.info("Frida 脚本加载成功，decrypt 方法可用")
                    break
            except Exception as e:
                logging.debug(f"等待 exports: {e}")
                continue
        
        if not script_loaded:
            logging.error("脚本初始化超时或失败")
            if script_error:
                logging.error(f"错误信息: {script_error}")
            return
            
    except Exception as e:
        logging.error(f"加载 Frida 脚本失败: {e}")
        import traceback
        traceback.print_exc()
        return

    if output_dir is not None and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    temp_dir = tempfile.mkdtemp(prefix="qqmusic_")

    try:
        for root, _, files in os.walk(input_dir):
            for file in files:
                base, ext = os.path.splitext(file)
                if ext.lower() not in [".mflac", ".mgg"]:
                    continue

                logging.info(f"开始解密: {file}")

                src_abs_path = os.path.abspath(os.path.join(root, file))

                # 确定输出扩展名
                if output_format:
                    # 如果指定了输出格式，先解密为原始格式，再转换
                    temp_ext = ext.lower().replace("mflac", "flac").replace("mgg", "ogg")
                    output_ext = f".{output_format.lower()}"
                else:
                    # 否则直接使用默认格式
                    temp_ext = ext.lower().replace("mflac", "flac").replace("mgg", "ogg")
                    output_ext = temp_ext
                
                # 确定目标目录：如果未指定output_dir或处于替换模式，则输出到源文件所在目录
                if output_dir is None or replace_mode:
                    target_dir = os.path.dirname(src_abs_path)
                else:
                    target_dir = output_dir
                
                output_filename = base + output_ext
                output_file_path = os.path.join(target_dir, output_filename)

                if os.path.exists(output_file_path):
                    logging.info(f"已存在，跳过: {output_file_path}")
                    continue

                temp_src_path = os.path.join(temp_dir, hashlib.md5(file.encode()).hexdigest() + ext)
                shutil.copyfile(src_abs_path, temp_src_path)

                tmp_output_path = os.path.abspath(
                    os.path.join(temp_dir, hashlib.md5(file.encode()).hexdigest() + temp_ext)
                )
                os.makedirs(os.path.dirname(tmp_output_path), exist_ok=True)

                try:
                    # 第一步：解密
                    script.exports_sync.decrypt(temp_src_path, tmp_output_path)
                    
                    # 第二步：如果需要格式转换
                    if output_format and output_format.lower() != temp_ext.lstrip('.'):
                        logging.info(f"正在进行格式转换: {temp_ext} -> {output_ext}")
                        final_output_path = os.path.join(target_dir, base + output_ext)
                        
                        if convert_with_ffmpeg(tmp_output_path, final_output_path, output_format):
                            logging.info(f"解密并转换成功: {final_output_path}")
                            # 清理临时解密文件
                            try:
                                os.remove(tmp_output_path)
                            except Exception:
                                pass
                            # 如果是替换模式，删除源文件
                            if replace_mode:
                                try:
                                    os.remove(src_abs_path)
                                    logging.info(f"已删除源文件: {src_abs_path}")
                                except Exception as e:
                                    logging.warning(f"删除源文件失败: {e}")
                        else:
                            logging.error(f"格式转换失败，保留原始解密文件: {tmp_output_path}")
                            # 转换失败，使用原始解密文件
                            shutil.move(tmp_output_path, output_file_path)
                            logging.info(f"解密成功: {output_file_path}")
                            # 如果是替换模式，删除源文件
                            if replace_mode:
                                try:
                                    os.remove(src_abs_path)
                                    logging.info(f"已删除源文件: {src_abs_path}")
                                except Exception as e:
                                    logging.warning(f"删除源文件失败: {e}")
                    else:
                        # 不需要转换，直接移动文件
                        shutil.move(tmp_output_path, output_file_path)
                        logging.info(f"解密成功: {output_file_path}")
                        # 如果是替换模式，删除源文件
                        if replace_mode:
                            try:
                                os.remove(src_abs_path)
                                logging.info(f"已删除源文件: {src_abs_path}")
                            except Exception as e:
                                logging.warning(f"删除源文件失败: {e}")
                            
                except Exception as e:
                    logging.error(f"解密失败: {file} -> {e}")
                    try:
                        if os.path.exists(tmp_output_path):
                            os.remove(tmp_output_path)
                    except Exception:
                        pass
                    continue
    finally:
        session.detach()
        shutil.rmtree(temp_dir, ignore_errors=True)
        logging.info("所有任务已完成")


def decrypt_with_replace(input_dir, output_dir=None, output_format=None, replace_mode=False):
    """
    解密文件
    
    Args:
        input_dir: 输入目录（包含加密文件）
        output_dir: 输出目录，如果为 None 则输出到源文件所在目录
        output_format: 输出格式 (mp3, flac, ogg, wav, m4a)，None 则使用默认格式
        replace_mode: 是否为替换模式，如果是则在成功后删除源文件
    """
    if not os.path.exists(input_dir):
        logging.error(f"输入目录不存在: {input_dir}")
        return
    
    # 如果没有指定输出目录，则输出到源文件所在目录（保持目录结构）
    if output_dir is None:
        logging.info("📁 未指定输出目录，将输出到源文件所在目录")
        if replace_mode:
            logging.info("⚠️  替换模式：解密后将删除原始加密文件")
            confirm = input("确认继续？(y/n): ").strip().lower()
            if confirm != 'y':
                logging.info("已取消操作")
                return
    
    logging.info(f"开始解密任务")
    logging.info(f"输入目录: {input_dir}")
    if output_dir:
        logging.info(f"输出目录: {output_dir}")
    else:
        logging.info(f"输出位置: 源文件所在目录（保持目录结构）")
    if output_format:
        logging.info(f"目标格式: {output_format.upper()}")
    
    run_decrypt(input_dir, output_dir, output_format, replace_mode=replace_mode)


def cmd_decrypt(args):
    """解密命令入口"""
    # 解密模式
    if args.input:
        # 确定是否为替换模式（删除源文件）
        replace_mode = args.replace
        
        # 如果未指定输出目录，默认输出到源文件所在目录
        if not args.output:
            if replace_mode:
                # --replace 模式：需要用户确认
                decrypt_with_replace(args.input, output_dir=None, output_format=args.format, replace_mode=True)
            else:
                # 默认模式：不删除源文件
                decrypt_with_replace(args.input, output_dir=None, output_format=args.format, replace_mode=False)
        else:
            # 指定了输出目录
            if replace_mode:
                logging.warning("⚠️  同时指定了 --replace 和 -o，将在输出后删除源文件")
            decrypt_with_replace(args.input, args.output, output_format=args.format, replace_mode=replace_mode)
    else:
        logging.error("请指定输入目录 (-i)，或使用 'list' 命令列出歌曲")
        sys.exit(1)


def cmd_list(args):
    """列出歌曲命令入口"""
    directory = args.directory if args.directory else None
    
    # 处理扩展名参数
    extensions = None
    if args.extensions:
        # 支持逗号分隔的多个扩展名
        extensions = [ext.strip() for ext in args.extensions.split(',')]
    
    list_download_songs(directory, extensions)


# ==================== 音频格式转换模块 ====================


def extract_metadata_with_mutagen(input_file):
    """
    使用 mutagen 提取源文件的元数据
    
    Args:
        input_file: 输入文件路径
    
    Returns:
        dict: 元数据字典 {'title': ..., 'artist': ..., 'album': ..., ...}
    """
    if not MUTAGEN_AVAILABLE:
        return {}
    
    try:
        ext = os.path.splitext(input_file)[1].lower()
        metadata = {}
        
        if ext == '.ogg':
            audio = OggVorbis(input_file)
            # OGG Vorbis 标签
            if 'title' in audio:
                metadata['title'] = str(audio['title'][0])
            if 'artist' in audio:
                metadata['artist'] = str(audio['artist'][0])
            if 'album' in audio:
                metadata['album'] = str(audio['album'][0])
            if 'date' in audio:
                metadata['date'] = str(audio['date'][0])
            if 'genre' in audio:
                metadata['genre'] = str(audio['genre'][0])
            if 'tracknumber' in audio:
                metadata['tracknumber'] = str(audio['tracknumber'][0])
        elif ext in ['.flac', '.mflac']:
            audio = FLAC(input_file)
            if 'title' in audio:
                metadata['title'] = str(audio['title'][0])
            if 'artist' in audio:
                metadata['artist'] = str(audio['artist'][0])
            if 'album' in audio:
                metadata['album'] = str(audio['album'][0])
            if 'date' in audio:
                metadata['date'] = str(audio['date'][0])
            if 'genre' in audio:
                metadata['genre'] = str(audio['genre'][0])
            if 'tracknumber' in audio:
                metadata['tracknumber'] = str(audio['tracknumber'][0])
        else:
            # 尝试通用方法
            try:
                audio = MP3(input_file, ID3=ID3)
                if audio.tags:
                    if 'TIT2' in audio.tags:
                        metadata['title'] = str(audio.tags['TIT2'])
                    if 'TPE1' in audio.tags:
                        metadata['artist'] = str(audio.tags['TPE1'])
                    if 'TALB' in audio.tags:
                        metadata['album'] = str(audio.tags['TALB'])
                    if 'TDRC' in audio.tags:
                        metadata['date'] = str(audio.tags['TDRC'])
                    if 'TCON' in audio.tags:
                        metadata['genre'] = str(audio.tags['TCON'])
            except:
                pass
        
        if metadata:
            logging.info(f"提取到元数据: {metadata}")
        
        return metadata
        
    except Exception as e:
        logging.warning(f"提取元数据失败: {e}")
        return {}


def write_mp3_metadata(output_file, metadata):
    """
    使用 mutagen 为 MP3 文件写入元数据
    
    Args:
        output_file: MP3 文件路径
        metadata: 元数据字典
    """
    if not MUTAGEN_AVAILABLE or not metadata:
        return
    
    try:
        # 读取或创建 ID3 标签
        try:
            audio = MP3(output_file, ID3=ID3)
        except:
            audio = MP3(output_file)
            audio.add_tags()
        
        # 写入元数据
        if 'title' in metadata:
            audio.tags['TIT2'] = TIT2(encoding=3, text=metadata['title'])
        if 'artist' in metadata:
            audio.tags['TPE1'] = TPE1(encoding=3, text=metadata['artist'])
        if 'album' in metadata:
            audio.tags['TALB'] = TALB(encoding=3, text=metadata['album'])
        if 'date' in metadata:
            audio.tags['TDRC'] = TDRC(encoding=3, text=metadata['date'])
        if 'genre' in metadata:
            audio.tags['TCON'] = TCON(encoding=3, text=metadata['genre'])
        if 'tracknumber' in metadata:
            audio.tags['TRCK'] = TRCK(encoding=3, text=metadata['tracknumber'])
        
        audio.save()
        logging.info(f"✅ 元数据写入成功: {list(metadata.keys())}")
        
    except Exception as e:
        logging.error(f"写入元数据失败: {e}")

def check_ffmpeg():
    """检查ffmpeg是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=False,  # 使用二进制模式避免编码问题
                              timeout=5)
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def get_audio_info(input_file):
    """
    获取音频文件的技术信息
    
    Args:
        input_file: 输入文件路径
    
    Returns:
        dict: 包含音频信息的字典 {'bitrate': 码率(bps), 'sample_rate': 采样率, 'bits_per_sample': 位深度, 'codec': 编码器}
              失败返回 None
    """
    if not check_ffmpeg():
        return None
    
    try:
        # 使用 ffprobe 获取音频信息
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'stream=bit_rate,sample_rate,bits_per_sample,codec_name,channels',
            '-of', 'json',
            input_file
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            timeout=10
        )
        
        if result.returncode != 0:
            logging.warning(f"ffprobe 执行失败: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
        
        import json
        info = json.loads(result.stdout.decode('utf-8', errors='ignore'))
        
        if 'streams' not in info or len(info['streams']) == 0:
            return None
        
        stream = info['streams'][0]
        
        audio_info = {
            'bitrate': int(stream.get('bit_rate', 0)) if stream.get('bit_rate') else None,
            'sample_rate': int(stream.get('sample_rate', 44100)),
            'bits_per_sample': int(stream.get('bits_per_sample', 16)) if stream.get('bits_per_sample') else None,
            'codec': stream.get('codec_name', 'unknown'),
            'channels': int(stream.get('channels', 2))
        }
        
        logging.debug(f"音频信息: {audio_info}")
        return audio_info
        
    except Exception as e:
        logging.warning(f"获取音频信息失败: {e}")
        return None


def calculate_quality_params(source_info, output_format, input_file=None):
    """
    根据源文件信息计算目标格式的编码参数
    
    Args:
        source_info: 源文件音频信息字典
        output_format: 目标格式 (mp3, flac, ogg, wav, m4a)
        input_file: 输入文件路径（用于检测文件扩展名）
    
    Returns:
        list: ffmpeg 编码参数字典
    """
    params = []
    
    # 如果无法获取源文件信息，使用默认高质量参数
    if source_info is None:
        logging.info("无法检测源文件信息，使用默认高质量参数")
        if output_format == 'mp3':
            params.extend(['-codec:a', 'libmp3lame', '-q:a', '2'])
        elif output_format == 'flac':
            params.extend(['-codec:a', 'flac', '-compression_level', '5'])
        elif output_format == 'ogg':
            params.extend(['-codec:a', 'libvorbis', '-q:a', '6'])
        elif output_format == 'wav':
            params.extend(['-codec:a', 'pcm_s16le'])
        elif output_format == 'm4a':
            params.extend(['-codec:a', 'aac', '-b:a', '256k'])
        return params
    
    source_bitrate = source_info.get('bitrate')  # bps
    source_codec = source_info.get('codec', '')
    source_bits = source_info.get('bits_per_sample', 16)
    
    # 判断源文件是否为无损格式
    is_lossless_source = source_codec in ['flac', 'alac', 'ape', 'wavpack', 'pcm_s16le', 'pcm_s24le', 'pcm_f32le']
    
    if output_format == 'mp3':
        params.extend(['-codec:a', 'libmp3lame'])
        
        # 特别优化：OGG 转 MP3
        source_ext = os.path.splitext(input_file)[1].lower() if input_file else ''
        
        if source_codec == 'vorbis' or source_ext == '.ogg':
            # OGG Vorbis 转 MP3：使用固定码率而非 VBR，更可控
            if source_bitrate and source_bitrate > 0:
                source_kbps = source_bitrate // 1000
                # OGG 的 bit_rate 可能不准确，使用更保守的策略
                # 对于 OGG，通常质量等级和码率对应关系：
                # q4 ≈ 128kbps, q5 ≈ 160kbps, q6 ≈ 192kbps
                # 使用 80% 作为目标，避免文件膨胀
                target_kbps = int(source_kbps * 0.8)
                # 限制在合理范围内（不超过 192kbps，除非源文件很高）
                target_kbps = max(128, min(target_kbps, 192))
                # 对齐到标准码率
                if target_kbps <= 128:
                    target_kbps = 128
                elif target_kbps <= 160:
                    target_kbps = 160
                else:
                    target_kbps = 192
                
                params.extend(['-b:a', f'{target_kbps}k'])
                logging.info(f"OGG转MP3: 源码率~{source_kbps}kbps → 目标码率{target_kbps}kbps (保守策略，避免膨胀)")
            else:
                # 无法检测码率，使用保守的中等质量
                params.extend(['-b:a', '160k'])
                logging.info("OGG转MP3: 无法检测码率，使用默认 160kbps")
        elif is_lossless_source:
            # 无损源：使用高质量 VBR
            params.extend(['-q:a', '2'])  # ~190-210kbps
            logging.info("检测到无损源文件，使用 MP3 VBR 高质量模式 (~190-210kbps)")
        elif source_bitrate:
            # 其他有损源：根据源码率调整
            source_kbps = source_bitrate // 1000
            if source_kbps <= 128:
                params.extend(['-q:a', '4'])  # ~160kbps，略高于源
                logging.info(f"检测到低码率源 ({source_kbps}kbps)，使用 MP3 VBR 中等质量 (~160kbps)")
            elif source_kbps <= 192:
                params.extend(['-q:a', '3'])  # ~175kbps
                logging.info(f"检测到中码率源 ({source_kbps}kbps)，使用 MP3 VBR 中高质量 (~175kbps)")
            else:
                params.extend(['-q:a', '2'])  # ~190-210kbps
                logging.info(f"检测到高码率源 ({source_kbps}kbps)，使用 MP3 VBR 高质量 (~190-210kbps)")
        else:
            params.extend(['-q:a', '2'])  # 默认高质量
    
    elif output_format == 'flac':
        params.extend(['-codec:a', 'flac', '-compression_level', '5'])
        if is_lossless_source:
            logging.info("无损转无损，保持原始品质")
        else:
            logging.info("有损转无损（FLAC），注意：不会提升音质，仅改变容器格式")
    
    elif output_format == 'ogg':
        params.extend(['-codec:a', 'libvorbis'])
        
        if is_lossless_source:
            params.extend(['-q:a', '6'])  # ~160-180kbps等效
            logging.info("检测到无损源文件，使用 OGG 高质量模式 (~160-180kbps等效)")
        elif source_bitrate:
            source_kbps = source_bitrate // 1000
            if source_kbps <= 128:
                params.extend(['-q:a', '4'])  # ~128kbps等效
                logging.info(f"检测到低码率源 ({source_kbps}kbps)，使用 OGG 中等质量 (~128kbps等效)")
            elif source_kbps <= 192:
                params.extend(['-q:a', '5'])  # ~160kbps等效
                logging.info(f"检测到中码率源 ({source_kbps}kbps)，使用 OGG 中高质量 (~160kbps等效)")
            else:
                params.extend(['-q:a', '6'])  # ~160-180kbps等效
                logging.info(f"检测到高码率源 ({source_kbps}kbps)，使用 OGG 高质量 (~160-180kbps等效)")
        else:
            params.extend(['-q:a', '6'])
    
    elif output_format == 'wav':
        # WAV 是无损格式，根据源文件位深度选择
        if source_bits and source_bits >= 24:
            params.extend(['-codec:a', 'pcm_s24le'])
            logging.info(f"检测到 {source_bits}位源文件，使用 24位 PCM")
        else:
            params.extend(['-codec:a', 'pcm_s16le'])
            logging.info(f"使用标准 16位 PCM (CD音质)")
    
    elif output_format == 'm4a':
        params.extend(['-codec:a', 'aac'])
        
        if is_lossless_source:
            params.extend(['-b:a', '256k'])
            logging.info("检测到无损源文件，使用 AAC 256kbps")
        elif source_bitrate:
            source_kbps = source_bitrate // 1000
            if source_kbps <= 128:
                params.extend(['-b:a', '128k'])
                logging.info(f"检测到低码率源 ({source_kbps}kbps)，使用 AAC 128kbps")
            elif source_kbps <= 192:
                params.extend(['-b:a', '192k'])
                logging.info(f"检测到中码率源 ({source_kbps}kbps)，使用 AAC 192kbps")
            else:
                params.extend(['-b:a', '256k'])
                logging.info(f"检测到高码率源 ({source_kbps}kbps)，使用 AAC 256kbps")
        else:
            params.extend(['-b:a', '256k'])
    
    else:
        params.extend(['-codec:a', 'copy'])
    
    return params


def convert_with_ffmpeg(input_file, output_file, output_format='mp3'):
    """
    使用ffmpeg转换音频格式
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
        output_format: 输出格式 (mp3, flac, ogg, wav, m4a)
    
    Returns:
        bool: 转换是否成功
    """
    if not check_ffmpeg():
        logging.error("ffmpeg 未安装或不在系统PATH中，请先安装 ffmpeg")
        logging.info("下载地址: https://ffmpeg.org/download.html")
        return False
    
    try:
        # 提取源文件元数据（在转换前）
        source_metadata = extract_metadata_with_mutagen(input_file)
        
        # 获取源文件信息
        source_info = get_audio_info(input_file)
        
        # 构建ffmpeg命令（保留源文件品质及元数据）
        cmd = ['ffmpeg', '-i', input_file, '-y']
        
        # 根据源文件信息和输出格式智能设置编码参数
        encoding_params = calculate_quality_params(source_info, output_format, input_file)
        cmd.extend(encoding_params)
        
        # 添加全局选项：保留所有元数据
        cmd.extend(['-map_metadata', '0'])
        
        # 特别处理：OGG/Vorbis Comments 转 ID3 标签需要额外映射
        if source_info and source_info.get('codec') == 'vorbis':
            # 确保正确映射 Vorbis Comments 到 ID3
            cmd.extend(['-id3v2_version', '3', '-write_id3v1', '1'])
            logging.info("检测到 OGG Vorbis，启用 ID3v2.3 + ID3v1 标签写入")
        
        # 对 MP4/M4A 格式添加 faststart 优化
        if output_format.lower() in ['m4a', 'mp4']:
            cmd.extend(['-movflags', '+faststart'])
        
        cmd.append(output_file)
        
        logging.debug(f"执行ffmpeg命令: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=False,  # 使用二进制模式避免编码问题
            timeout=60
        )
        
        if result.returncode == 0:
            logging.info(f"格式转换成功: {output_format.upper()}")
            
            # 对于 MP3 文件，使用 mutagen 手动写入元数据（更可靠）
            if output_format.lower() == 'mp3' and source_metadata:
                write_mp3_metadata(output_file, source_metadata)
            
            return True
        else:
            # 解码stderr时使用utf-8并忽略错误
            stderr_text = result.stderr.decode('utf-8', errors='ignore')
            logging.error(f"ffmpeg转换失败: {stderr_text}")
            return False
            
    except subprocess.TimeoutExpired:
        logging.error("ffmpeg转换超时")
        return False
    except Exception as e:
        logging.error(f"ffmpeg转换异常: {e}")
        return False


def convert_single_file(input_file, output_format='mp3', output_dir=None):
    """
    转换单个音频文件
    
    Args:
        input_file: 输入文件路径
        output_format: 输出格式
        output_dir: 输出目录，默认为输入文件的目录
    
    Returns:
        str: 输出文件路径，失败返回None
    """
    if not os.path.exists(input_file):
        logging.error(f"文件不存在: {input_file}")
        return None
    
    # 确定输出目录
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(input_file))
    else:
        output_dir = os.path.abspath(output_dir)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    # 获取文件名和扩展名
    filename = os.path.basename(input_file)
    base, ext = os.path.splitext(filename)
    
    # 生成输出文件名
    output_filename = base + f".{output_format.lower()}"
    output_file = os.path.join(output_dir, output_filename)
    
    # 检查是否已存在
    if os.path.exists(output_file):
        logging.info(f"文件已存在，跳过: {output_file}")
        return output_file
    
    logging.info(f"开始转换: {filename} -> {output_format.upper()}")
    
    # 执行转换
    success = convert_with_ffmpeg(input_file, output_file, output_format)
    
    if success:
        logging.info(f"转换成功: {output_file}")
        return output_file
    else:
        logging.error(f"转换失败: {filename}")
        return None


def convert_directory(input_dir, output_dir, output_format='mp3'):
    """
    批量转换目录下的所有音频文件
    
    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        output_format: 输出格式
    
    Returns:
        tuple: (success_count, fail_count) - 成功和失败的文件数量
    """
    if not os.path.exists(input_dir):
        logging.error(f"输入目录不存在: {input_dir}")
        return 0, 0
    
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    logging.info(f"批量转换: {input_dir} -> {output_dir} (格式: {output_format.upper()})")
    
    # 支持的输入格式
    supported_exts = {'.flac', '.ogg', '.mp3', '.wav', '.m4a', '.mflac', '.mgg'}
    
    success_count = 0
    fail_count = 0
    
    for root, _, files in os.walk(input_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in supported_exts:
                continue
            
            input_file = os.path.join(root, file)
            
            try:
                result = convert_single_file(input_file, output_format, output_dir)
                if result:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logging.error(f"处理文件失败 {file}: {e}")
                fail_count += 1
    
    logging.info(f"转换完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    return success_count, fail_count


def cmd_convert(args):
    """格式转换命令入口"""
    # 验证输出格式
    supported_formats = ['mp3', 'flac', 'ogg', 'wav', 'm4a']
    if args.format.lower() not in supported_formats:
        logging.error(f"不支持的输出格式: {args.format}")
        logging.info(f"支持的格式: {', '.join(supported_formats)}")
        sys.exit(1)
    
    # 检查ffmpeg
    if not check_ffmpeg():
        logging.error("ffmpeg 未安装或不在系统PATH中")
        logging.info("下载地址: https://ffmpeg.org/download.html")
        sys.exit(1)
    
    # 判断是文件还是目录
    if os.path.isfile(args.input):
        # 单文件转换
        result = convert_single_file(args.input, args.format, args.output)
        if result:
            print(f"\n✅ 转换成功: {result}")
            sys.exit(0)
        else:
            print("\n❌ 转换失败")
            sys.exit(1)
    elif os.path.isdir(args.input):
        # 批量转换
        if not args.output:
            logging.error("批量转换必须指定输出目录 (-o)")
            sys.exit(1)
        
        success, fail = convert_directory(args.input, args.output, args.format)
        
        print(f"\n{'='*50}")
        print(f"转换完成统计:")
        print(f"  成功: {success} 个文件")
        print(f"  失败: {fail} 个文件")
        print(f"{'='*50}")
        
        sys.exit(0 if fail == 0 else 1)
    else:
        logging.error(f"输入路径不存在: {args.input}")
        sys.exit(1)


# ==================== 空歌词删除模块 ====================

def should_delete_lrc(file_path):
    """
    检查lrc文件是否应该被删除
    
    Args:
        file_path: lrc文件路径
        
    Returns:
        bool: 如果文件内容匹配目标文本返回True，否则返回False
    """
    target_content = "[00:00:00]此歌曲为没有填词的纯音乐，请您欣赏"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return content == target_content
    except UnicodeDecodeError:
        # 尝试使用其他编码
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read().strip()
                return content == target_content
        except Exception:
            return False
    except Exception as e:
        logging.error(f"读取文件失败 {file_path}: {e}")
        return False


def delete_empty_lrc_files(directory):
    """
    遍历目录并删除空的lrc文件
    
    Args:
        directory: 要扫描的目录路径
    """
    if not os.path.exists(directory):
        logging.error(f"目录 '{directory}' 不存在")
        return
    
    if not os.path.isdir(directory):
        logging.error(f"'{directory}' 不是一个目录")
        return
    
    deleted_count = 0
    error_count = 0
    
    logging.info(f"开始扫描目录: {directory}")
    print("-" * 50)
    
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith('.lrc'):
                file_path = os.path.join(root, filename)
                
                if should_delete_lrc(file_path):
                    try:
                        os.remove(file_path)
                        print(f"已删除: {file_path}")
                        deleted_count += 1
                    except Exception as e:
                        logging.error(f"删除失败 {file_path}: {e}")
                        error_count += 1
    
    print("-" * 50)
    print(f"扫描完成!")
    print(f"共删除 {deleted_count} 个文件")
    if error_count > 0:
        print(f"{error_count} 个文件删除失败")


def cmd_clean_lrc(args):
    """清理空歌词命令入口"""
    directory = args.directory
    
    if not directory:
        logging.error("目录路径不能为空")
        sys.exit(1)
    
    # 确认操作
    print(f"\n即将扫描目录: {directory}")
    if not args.yes:
        confirm = input("确认继续? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("操作已取消")
            sys.exit(0)
    
    delete_empty_lrc_files(directory)


# ==================== 主程序入口 ====================

def main():
    """主函数 - CLI 入口"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    parser = argparse.ArgumentParser(
        description="QQ 音乐下载辅助工具 - 集成解密、格式转换、歌词清理等功能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
可用命令:
  decrypt     解密 QQ 音乐加密文件 (.mflac/.mgg)
  list        列出歌曲文件（支持目录和扩展名筛选）
  convert     音频格式转换 (需要 ffmpeg)
  clean-lrc   批量删除空歌词文件

示例用法:
  # 列出歌曲
  python main.py list                                       # 列出默认下载目录的歌曲
  python main.py list ./my_music                           # 列出指定目录的歌曲
  python main.py list -e mp3,flac                          # 只列出 MP3 和 FLAC 文件
  python main.py list ./music -e mgg,mflac                 # 列出指定目录的加密文件
  
  # 解密相关
  python main.py decrypt -i ./encrypted                      # 解密到源文件所在目录（保持目录结构）
  python main.py decrypt -i ./encrypted --replace             # 解密并删除原始加密文件
  python main.py decrypt -i ./encrypted -o ./decrypted        # 解密到指定目录
  python main.py decrypt -i ./encrypted -o ./mp3 -f mp3       # 解密并转换为 MP3
  python main.py decrypt -i ./encrypted -o ./flac -f flac     # 解密并转换为 FLAC
  python main.py decrypt -i ./encrypted -o ./mp3 -f mp3 --replace  # 转换后删除源文件
  
  # 格式转换
  python main.py convert -i song.flac -f mp3                   # 转换单个文件
  python main.py convert -i ./flac -o ./mp3 -f mp3            # 批量转换目录
  
  # 清理空歌词
  python main.py clean-lrc ./lyrics                           # 扫描并删除空歌词
  python main.py clean-lrc ./lyrics -y                        # 自动确认删除
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # ========== list 子命令 ==========
    list_parser = subparsers.add_parser('list', help='列出歌曲文件（支持目录和扩展名筛选）')
    list_parser.add_argument("directory", type=str, nargs='?', default=None,
                            help="要扫描的目录路径（不指定则使用默认下载目录）")
    list_parser.add_argument("-e", "--extensions", type=str, default=None,
                            help="文件扩展名筛选，多个用逗号分隔（如：mp3,flac,m4a）")
    
    # ========== decrypt 子命令 ==========
    decrypt_parser = subparsers.add_parser('decrypt', help='解密 QQ 音乐加密文件 (.mflac/.mgg)')
    decrypt_parser.add_argument("-i", "--input", type=str, 
                               help="输入目录（包含 .mflac/.mgg 文件）")
    decrypt_parser.add_argument("-o", "--output", type=str, default=None,
                               help="输出目录（不指定则输出到源文件所在目录，保持目录结构）")
    decrypt_parser.add_argument("-f", "--format", type=str, default=None,
                               help="输出格式 (mp3, flac, ogg, wav, m4a)，不指定则使用默认格式")
    decrypt_parser.add_argument("--replace", action="store_true",
                               help="替换模式：解密成功后删除原始加密文件")
    
    # ========== convert 子命令 ==========
    convert_parser = subparsers.add_parser('convert', help='音频格式转换 (需要 ffmpeg)')
    convert_parser.add_argument("-i", "--input", type=str, required=True,
                               help="输入文件或目录路径")
    convert_parser.add_argument("-o", "--output", type=str, default=None,
                               help="输出目录（不指定则使用输入文件所在目录）")
    convert_parser.add_argument("-f", "--format", type=str, default='mp3',
                               help="输出格式 (mp3, flac, ogg, wav, m4a)，默认: mp3")
    
    # ========== clean-lrc 子命令 ==========
    clean_lrc_parser = subparsers.add_parser('clean-lrc', help='批量删除空歌词文件')
    clean_lrc_parser.add_argument("directory", type=str, nargs='?', default=None,
                                 help="要扫描的目录路径")
    clean_lrc_parser.add_argument("-y", "--yes", action="store_true",
                                 help="自动确认，不提示")
    
    args = parser.parse_args()
    
    # 无参数时显示帮助
    if args.command is None:
        parser.print_help()
        sys.exit(0)
    
    # ========== 执行对应命令 ==========
    
    if args.command == 'list':
        cmd_list(args)
    
    elif args.command == 'decrypt':
        cmd_decrypt(args)
    
    elif args.command == 'convert':
        cmd_convert(args)
    
    elif args.command == 'clean-lrc':
        cmd_clean_lrc(args)


if __name__ == "__main__":
    main()

