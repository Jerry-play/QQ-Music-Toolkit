# -*- coding: utf-8 -*-
"""
音频格式转换工具
支持将解密后的音频文件转换为不同格式，并添加元数据
"""

import os
import sys
import argparse
import logging
import subprocess
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, COMM, APIC
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logging.warning("mutagen 未安装，将无法手动写入元数据")


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
            # OGG Vorbis 转 MP3：使用 VBR 而非 CBR，质量/体积比更优
            if source_bitrate and source_bitrate > 0:
                source_kbps = source_bitrate // 1000
                # OGG 的 bit_rate 不准确，使用保守策略
                # LAME VBR 质量等级与码率对应：
                # -V4 ≈ 140-185kbps (透明音质起点)
                # -V5 ≈ 130-170kbps (良好质量)
                # -V6 ≈ 115-150kbps (中等质量)
                target_kbps = int(source_kbps * 0.75)  # 更保守的75%
                
                if target_kbps < 140:
                    params.extend(['-q:a', '6'])  # ~130kbps
                    logging.info(f"OGG转MP3: 源码率~{source_kbps}kbps → VBR -q:a 6 (~130kbps，节省空间)")
                elif target_kbps < 165:
                    params.extend(['-q:a', '5'])  # ~150kbps
                    logging.info(f"OGG转MP3: 源码率~{source_kbps}kbps → VBR -q:a 5 (~150kbps，平衡模式)")
                else:
                    params.extend(['-q:a', '4'])  # ~165kbps
                    logging.info(f"OGG转MP3: 源码率~{source_kbps}kbps → VBR -q:a 4 (~165kbps，高质量)")
            else:
                # 无法检测码率，使用平衡质量
                params.extend(['-q:a', '5'])
                logging.info("OGG转MP3: 无法检测码率，使用默认 VBR -q:a 5 (~150kbps)")
        elif is_lossless_source:
            # 无损源：使用 VBR 高质量（透明音质）
            params.extend(['-q:a', '2'])  # ~190-210kbps，透明音质
            logging.info("检测到无损源文件，使用 MP3 VBR -q:a 2 (透明音质 ~190-210kbps)")
        elif source_bitrate:
            # 其他有损源：根据源码率智能调整
            source_kbps = source_bitrate // 1000
            if source_kbps <= 128:
                params.extend(['-q:a', '6'])  # ~130kbps，略高于源
                logging.info(f"检测到低码率源 ({source_kbps}kbps)，使用 MP3 VBR -q:a 6 (~130kbps)")
            elif source_kbps <= 160:
                params.extend(['-q:a', '5'])  # ~150kbps
                logging.info(f"检测到中低码率源 ({source_kbps}kbps)，使用 MP3 VBR -q:a 5 (~150kbps)")
            elif source_kbps <= 192:
                params.extend(['-q:a', '4'])  # ~165kbps
                logging.info(f"检测到中高码率源 ({source_kbps}kbps)，使用 MP3 VBR -q:a 4 (~165kbps)")
            else:
                params.extend(['-q:a', '2'])  # ~190kbps
                logging.info(f"检测到高码率源 ({source_kbps}kbps)，使用 MP3 VBR -q:a 2 (~190kbps)")
        else:
            params.extend(['-q:a', '4'])  # 默认平衡质量
    
    elif output_format == 'flac':
        # FLAC 无损压缩，compression_level 只影响编码速度，不影响音质
        # 等级 0-8，5 是平衡点（速度和压缩率）
        params.extend(['-codec:a', 'flac', '-compression_level', '5'])
        if is_lossless_source:
            logging.info("无损转无损（FLAC），保持原始品质")
        else:
            logging.warning("有损转无损（FLAC）：不会提升音质，仅改变容器格式")
    
    elif output_format == 'ogg':
        # OGG Vorbis 使用 VBR 质量等级
        # q0-q10，通常 q4-q6 是最佳平衡点
        params.extend(['-codec:a', 'libvorbis'])
        
        if is_lossless_source:
            params.extend(['-q:a', '5'])  # ~160kbps，高质量
            logging.info("检测到无损源文件，使用 OGG -q:a 5 (~160kbps，高质量)")
        elif source_bitrate:
            source_kbps = source_bitrate // 1000
            if source_kbps <= 128:
                params.extend(['-q:a', '3'])  # ~112kbps
                logging.info(f"检测到低码率源 ({source_kbps}kbps)，使用 OGG -q:a 3 (~112kbps)")
            elif source_kbps <= 160:
                params.extend(['-q:a', '4'])  # ~128kbps
                logging.info(f"检测到中低码率源 ({source_kbps}kbps)，使用 OGG -q:a 4 (~128kbps)")
            elif source_kbps <= 192:
                params.extend(['-q:a', '5'])  # ~160kbps
                logging.info(f"检测到中高码率源 ({source_kbps}kbps)，使用 OGG -q:a 5 (~160kbps)")
            else:
                params.extend(['-q:a', '6'])  # ~192kbps
                logging.info(f"检测到高码率源 ({source_kbps}kbps)，使用 OGG -q:a 6 (~192kbps)")
        else:
            params.extend(['-q:a', '5'])  # 默认高质量
    
    elif output_format == 'wav':
        # WAV 是无损格式，根据源文件位深度选择
        if source_bits and source_bits >= 24:
            params.extend(['-codec:a', 'pcm_s24le'])
            logging.info(f"检测到 {source_bits}位源文件，使用 24位 PCM")
        else:
            params.extend(['-codec:a', 'pcm_s16le'])
            logging.info(f"使用标准 16位 PCM (CD音质)")
    
    elif output_format == 'm4a':
        # AAC 编码效率高于 MP3，同样码率下音质更好
        params.extend(['-codec:a', 'aac'])
        
        if is_lossless_source:
            params.extend(['-b:a', '192k'])  # AAC 192k ≈ MP3 256k
            logging.info("检测到无损源文件，使用 AAC 192kbps (≈MP3 256kbps)")
        elif source_bitrate:
            source_kbps = source_bitrate // 1000
            if source_kbps <= 128:
                params.extend(['-b:a', '96k'])  # AAC 96k ≈ MP3 128k
                logging.info(f"检测到低码率源 ({source_kbps}kbps)，使用 AAC 96kbps (≈MP3 128kbps)")
            elif source_kbps <= 160:
                params.extend(['-b:a', '128k'])
                logging.info(f"检测到中低码率源 ({source_kbps}kbps)，使用 AAC 128kbps")
            elif source_kbps <= 192:
                params.extend(['-b:a', '160k'])
                logging.info(f"检测到中高码率源 ({source_kbps}kbps)，使用 AAC 160kbps")
            else:
                params.extend(['-b:a', '192k'])
                logging.info(f"检测到高码率源 ({source_kbps}kbps)，使用 AAC 192kbps")
        else:
            params.extend(['-b:a', '160k'])  # 默认平衡质量
    
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


def main():
    """命令行入口"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    parser = argparse.ArgumentParser(
        description="音频格式转换工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 转换单个文件
  python audio_converter.py -i song.flac -f mp3
  
  # 转换单个文件到指定目录
  python audio_converter.py -i song.flac -o ./converted -f mp3
  
  # 批量转换目录
  python audio_converter.py -i ./flac_files -o ./mp3_files -f mp3
  
  # 转换为其他格式
  python audio_converter.py -i ./input -o ./output -f wav
  python audio_converter.py -i ./input -o ./output -f m4a
        """
    )
    
    parser.add_argument("-i", "--input", type=str, required=True,
                       help="输入文件或目录路径")
    parser.add_argument("-o", "--output", type=str, default=None,
                       help="输出目录（不指定则使用输入文件所在目录）")
    parser.add_argument("-f", "--format", type=str, default='mp3',
                       help="输出格式 (mp3, flac, ogg, wav, m4a)，默认: mp3")
    
    args = parser.parse_args()
    
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
            parser.error("批量转换必须指定输出目录 (-o)")
        
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


if __name__ == "__main__":
    main()
