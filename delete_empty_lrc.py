#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量删除空歌词文件工具
遍历指定目录下的所有.lrc文件，如果内容匹配特定文本则删除
"""

import os
import sys


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
        print(f"读取文件失败 {file_path}: {e}")
        return False


def delete_empty_lrc_files(directory):
    """
    遍历目录并删除空的lrc文件
    
    Args:
        directory: 要扫描的目录路径
    """
    if not os.path.exists(directory):
        print(f"错误: 目录 '{directory}' 不存在")
        return
    
    if not os.path.isdir(directory):
        print(f"错误: '{directory}' 不是一个目录")
        return
    
    deleted_count = 0
    error_count = 0
    
    print(f"开始扫描目录: {directory}")
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
                        print(f"删除失败 {file_path}: {e}")
                        error_count += 1
    
    print("-" * 50)
    print(f"扫描完成!")
    print(f"共删除 {deleted_count} 个文件")
    if error_count > 0:
        print(f"{error_count} 个文件删除失败")


def main():
    """主函数"""
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = input("请输入要扫描的目录路径: ").strip()
    
    if not directory:
        print("错误: 目录路径不能为空")
        sys.exit(1)
    
    # 确认操作
    print(f"\n即将扫描目录: {directory}")
    confirm = input("确认继续? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("操作已取消")
        sys.exit(0)
    
    delete_empty_lrc_files(directory)


if __name__ == "__main__":
    main()

