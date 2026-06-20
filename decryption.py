# -*- coding: utf-8 -*-

import frida
import os
import sys
import hashlib
import argparse
import logging
import shutil
import tempfile


def list_download_songs():
    download_dir = os.path.join(os.path.expanduser("~"), "Music", "VipSongsDownload")
    # 如果默认目录不存在，可以尝试自定义路径
    # download_dir = os.path.join("E:", "music", "VipSongsDownload")
    if not os.path.exists(download_dir):
        logging.error(f"默认下载目录不存在：{download_dir}")
        return
    logging.info(f"QQ 音乐下载目录：{download_dir}")
    exts = {".mflac", ".mgg", ".ogg", ".flac", ".mp3", ".m4a"}
    count = 0
    for root, _, files in os.walk(download_dir):
        for file in files:
            if os.path.splitext(file)[1].lower() in exts:
                count += 1
                full_path = os.path.join(root, file)
                rel = os.path.relpath(full_path, download_dir)
                print(f"{count:4d}. {rel}")
    logging.info(f"共找到 {count} 个文件")


def run_decrypt(input_dir, output_dir):
    if not os.path.exists(input_dir):
        logging.error(f"输入目录不存在: {input_dir}")
        return

    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)

    logging.info(f"解密模式: 输入={input_dir}, 输出={output_dir}")
    
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
        import time
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

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    temp_dir = tempfile.mkdtemp(prefix="qqmusic_")

    try:
        for root, _, files in os.walk(input_dir):
            for file in files:
                base, ext = os.path.splitext(file)
                if ext.lower() not in [".mflac", ".mgg"]:
                    continue

                logging.info(f"开始解密: {file}")

                # 确定输出扩展名（直接替换）
                new_ext = ext.lower().replace("mflac", "flac").replace("mgg", "ogg")
                output_filename = base + new_ext
                output_file_path = os.path.join(output_dir, output_filename)

                if os.path.exists(output_file_path):
                    logging.info(f"已存在，跳过: {output_file_path}")
                    continue

                src_abs_path = os.path.abspath(os.path.join(root, file))
                temp_src_path = os.path.join(temp_dir, hashlib.md5(file.encode()).hexdigest() + ext)
                shutil.copyfile(src_abs_path, temp_src_path)

                tmp_output_path = os.path.abspath(
                    os.path.join(temp_dir, hashlib.md5(file.encode()).hexdigest() + new_ext)
                )
                os.makedirs(os.path.dirname(tmp_output_path), exist_ok=True)

                try:
                    script.exports_sync.decrypt(temp_src_path, tmp_output_path)
                    # 使用 shutil.move 替代 os.rename，支持跨磁盘移动
                    shutil.move(tmp_output_path, output_file_path)
                    logging.info(f"解密成功: {output_file_path}")
                            
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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-l", "--list", action="store_true")
    parser.add_argument("-i", "--input", type=str, required=False)
    parser.add_argument("-o", "--output", type=str, required=False)
    args = parser.parse_args()

    if len(sys.argv) == 1:
        print("作者: 唐晓宇\n")
        print("命令用法:")
        print("  列出 QQ 音乐默认下载目录下的歌曲: decryption.py -l")
        print("  注：默认目录 C:\\Users\\<当前用户名>\\Music\\VipSongsDownload")
        print("  解密转换指定目录下的歌曲（可批量转换）:")
        print("  decryption.py -i input -o output")
        sys.exit(0)

    if args.list:
        list_download_songs()
        sys.exit(0)

    if not args.input or not args.output:
        parser.error("解密模式需要提供 -i <输入目录> 和 -o <输出目录>；如仅想查看，请使用 -l")
    run_decrypt(args.input, args.output)
