# QQ 音乐音频解密工具

一个功能完善的 QQ 音乐辅助工具，支持解密加密音频文件、格式转换、歌词清理等功能。

## 主要功能

- **音频解密**：将 QQ 音乐下载的 `.mflac` / `.mgg` 加密文件解密为标准音频格式（`.flac` / `.ogg`）
- **格式转换**：支持转换为 MP3、FLAC、OGG、WAV、M4A 等多种格式，智能保留元数据
- **批量处理**：支持单文件和目录批量处理
- **歌词清理**：自动删除无歌词的纯音乐标记文件
- **歌曲列表**：快速查看下载目录中的歌曲文件

## 环境准备

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 ffmpeg（格式转换必需）

- **Windows**: 从 [ffmpeg 官网](https://ffmpeg.org/download.html) 下载并添加到系统 PATH
- **Linux**: `sudo apt-get install ffmpeg` 或 `sudo yum install ffmpeg`
- **macOS**: `brew install ffmpeg`

验证安装：
```bash
ffmpeg -version
```

### 3. 启动 QQ 音乐客户端

解密功能需要 QQ 音乐客户端处于运行状态，工具通过 Frida 注入进程进行解密。

## 使用方法

### 基本命令格式

```bash
python main.py <command> [options]
```

### 可用命令

#### 1. 列出歌曲文件

查看 QQ 音乐下载目录中的歌曲文件列表。

```bash
# 列出默认下载目录的歌曲
python main.py list

# 列出指定目录的歌曲
python main.py list ./my_music

# 只列出特定格式的文件
python main.py list -e mp3,flac
python main.py list ./music -e mgg,mflac
```

**参数说明：**
- `directory`：要扫描的目录路径（可选，不指定则使用默认下载目录）
- `-e, --extensions`：文件扩展名筛选，多个用逗号分隔

**默认下载目录：**
- Windows: `C:\Users\<用户名>\Music\VipSongsDownload`

---

#### 2. 解密加密文件

将 `.mflac` / `.mgg` 加密文件解密为标准音频格式。

```bash
# 解密到源文件所在目录（保持目录结构）
python main.py decrypt -i ./encrypted

# 解密并删除原始加密文件（替换模式）
python main.py decrypt -i ./encrypted --replace

# 解密到指定目录
python main.py decrypt -i ./encrypted -o ./decrypted

# 解密并转换为 MP3 格式
python main.py decrypt -i ./encrypted -o ./mp3 -f mp3

# 解密并转换为 FLAC 格式
python main.py decrypt -i ./encrypted -o ./flac -f flac

# 解密转换后删除源文件
python main.py decrypt -i ./encrypted -o ./mp3 -f mp3 --replace
```

**参数说明：**
- `-i, --input`：输入目录（包含 `.mflac` / `.mgg` 文件）**必需**
- `-o, --output`：输出目录（可选，不指定则输出到源文件所在目录）
- `-f, --format`：输出格式（mp3, flac, ogg, wav, m4a），不指定则使用默认格式
- `--replace`：替换模式，解密成功后删除原始加密文件

**支持的格式转换：**
- `.mflac` → `.flac`（默认）→ 可转换为其他格式
- `.mgg` → `.ogg`（默认）→ 可转换为其他格式

---

#### 3. 音频格式转换

将音频文件转换为不同格式，智能保留元数据和音质。

```bash
# 转换单个文件
python main.py convert -i song.flac -f mp3

# 转换单个文件到指定目录
python main.py convert -i song.flac -o ./converted -f mp3

# 批量转换目录
python main.py convert -i ./flac_files -o ./mp3_files -f mp3

# 转换为其他格式
python main.py convert -i ./input -o ./output -f wav
python main.py convert -i ./input -o ./output -f m4a
```

**参数说明：**
- `-i, --input`：输入文件或目录路径 **必需**
- `-o, --output`：输出目录（可选，不指定则使用输入文件所在目录；批量转换时必需）
- `-f, --format`：输出格式（mp3, flac, ogg, wav, m4a），默认: mp3

**智能编码特性：**
- 自动检测源文件码率和编码器
- 无损源文件使用高质量编码
- 有损源文件采用保守策略避免音质损失
- 自动提取和写入元数据（标题、艺术家、专辑等）
- OGG Vorbis 转 MP3 时启用 ID3v2.3 + ID3v1 标签

---

#### 4. 清理空歌词文件

删除内容为"此歌曲为没有填词的纯音乐，请您欣赏"的 `.lrc` 文件。

```bash
# 扫描并删除空歌词（会提示确认）
python main.py clean-lrc ./lyrics

# 自动确认删除（无提示）
python main.py clean-lrc ./lyrics -y
```

**参数说明：**
- `directory`：要扫描的目录路径 **必需**
- `-y, --yes`：自动确认，不提示

---

## 💡 使用示例

### 场景 1：批量解密并转换所有歌曲为 MP3

```bash
# 第一步：查看有哪些加密文件
python main.py list -e mgg,mflac

# 第二步：解密并转换为 MP3
python main.py decrypt -i "C:\Users\YourName\Music\VipSongsDownload" -o ./mp3_songs -f mp3
```

### 场景 2：整理音乐库

```bash
# 解密所有加密文件到源目录
python main.py decrypt -i ./music_collection --replace

# 将所有 FLAC 转换为 MP3（节省空间）
python main.py convert -i ./music_collection -o ./mp3_version -f mp3

# 清理无用的歌词文件
python main.py clean-lrc ./music_collection -y
```

### 场景 3：单文件快速转换

```bash
# 转换单个 OGG 文件为 MP3
python main.py convert -i song.ogg -f mp3
```

---

## ⚙️ 技术细节

### 解密原理

本工具使用 Frida 动态插桩技术，注入 QQMusic.exe 进程，调用其内部的 `EncAndDesMediaFile` 类进行解密。解密过程在内存中完成，无需修改 QQ 音乐客户端。

### 格式转换策略

工具会根据源文件信息智能选择编码参数：

| 源文件类型 | MP3 目标 | FLAC 目标 | OGG 目标 |
|-----------|---------|----------|---------|
| 无损 (FLAC/ALAC) | VBR -q:a 2 (~190kbps) | 无损压缩 level 5 | -q:a 5 (~160kbps) |
| 有损高码率 (>192kbps) | VBR -q:a 2 (~190kbps) | 无损压缩 | -q:a 6 (~192kbps) |
| 有损中码率 (128-192kbps) | VBR -q:a 4-5 (~150-165kbps) | 无损压缩 | -q:a 4-5 (~128-160kbps) |
| 有损低码率 (<128kbps) | VBR -q:a 6 (~130kbps) | 无损压缩 | -q:a 3 (~112kbps) |

**注意：** 有损转无损（如 MP3 → FLAC）不会提升音质，仅改变容器格式。

### 元数据处理

- 使用 `mutagen` 库提取和写入元数据
- 支持 OGG Vorbis Comments ↔ ID3 标签转换
- 保留标题、艺术家、专辑、日期、流派、音轨号等信息
- MP3 文件额外写入 ID3v2.3 和 ID3v1 双标签确保兼容性

---

## ⚠️ 注意事项

1. **QQ 音乐必须运行**：解密功能需要 QQ 音乐客户端处于运行状态
2. **管理员权限**：如果 Frida 附加失败，尝试以管理员身份运行命令行
3. **路径支持中文**：工具内部已处理中文路径兼容性问题
4. **磁盘空间**：批量转换时确保有足够的临时空间
5. **版权说明**：请仅用于个人学习研究，尊重音乐版权
6. **版本兼容**：如遇到解密失败，可能是 QQ 音乐版本更新导致，请检查 `hook_qq_music.js` 中的函数签名

---

## 🛠️ 故障排除

### 问题 1：Frida 附加失败

```
frida.ProcessNotFoundError: unable to find process with name 'QQMusic.exe'
```

**解决方案：**
- 确保 QQ 音乐客户端已启动
- 检查进程名称是否为 `QQMusic.exe`（任务管理器中查看）
- 尝试以管理员身份运行

### 问题 2：脚本初始化失败

```
部分导出函数未找到，请检查 QQMusicCommon.dll 版本
```

**解决方案：**
- QQ 音乐版本可能已更新，需要更新 `hook_qq_music.js` 中的函数签名
- 参考原项目或使用 Dependency Walker 查看新的导出函数名

### 问题 3：ffmpeg 未找到

```
ffmpeg 未安装或不在系统PATH中
```

**解决方案：**
- 下载 ffmpeg 并添加到系统 PATH
- 验证：在命令行输入 `ffmpeg -version` 应能看到版本信息

### 问题 4：转换后元数据丢失

**解决方案：**
- 确保安装了 `mutagen` 库：`pip install mutagen`
- 检查源文件是否包含元数据
- OGG 转 MP3 时工具会自动处理标签映射

---

## 依赖项

- **frida** (17.7.3)：动态插桩框架
- **mutagen** (1.47.0)：音频元数据处理
- **ffmpeg**：音频格式转换（需单独安装）

---

## 致谢

本项目核心解密代码来自以下开源项目改进：

- [QQ-Music-Audio-Decryption-Tool](https://github.com/HanZeYu-momo/QQ-Music-Audio-Decryption-Tool) - 原始 Frida 解密方案

感谢原作者的贡献！

---

