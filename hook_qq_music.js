const TARGET_DLL = "QQMusicCommon.dll";

console.log("[*] 开始加载 Hook 脚本...");

// 等待 DLL 加载
var targetModule = null;
for (var i = 0; i < 100; i++) {
  try {
    targetModule = Process.getModuleByName(TARGET_DLL);
    if (targetModule !== null) break;
  } catch(e) {}
  Thread.sleep(0.1);
}

if (targetModule === null) {
  throw new Error("无法找到 " + TARGET_DLL);
}

console.log("[+] 找到模块: " + targetModule.name + " at " + targetModule.base);

// 从模块对象直接获取导出函数地址（更可靠）
var EncAndDesMediaFileConstructorAddr = targetModule.findExportByName("??0EncAndDesMediaFile@@QAE@XZ");
var EncAndDesMediaFileDestructorAddr = targetModule.findExportByName("??1EncAndDesMediaFile@@QAE@XZ");
var EncAndDesMediaFileOpenAddr = targetModule.findExportByName("?Open@EncAndDesMediaFile@@QAE_NPB_W_N1@Z");
var EncAndDesMediaFileGetSizeAddr = targetModule.findExportByName("?GetSize@EncAndDesMediaFile@@QAEKXZ");
var EncAndDesMediaFileReadAddr = targetModule.findExportByName("?Read@EncAndDesMediaFile@@QAEKPAEK_J@Z");

// 验证所有地址
console.log("[*] 检查导出函数地址:");
console.log("  Constructor: " + EncAndDesMediaFileConstructorAddr);
console.log("  Destructor: " + EncAndDesMediaFileDestructorAddr);
console.log("  Open: " + EncAndDesMediaFileOpenAddr);
console.log("  GetSize: " + EncAndDesMediaFileGetSizeAddr);
console.log("  Read: " + EncAndDesMediaFileReadAddr);

if (EncAndDesMediaFileConstructorAddr === null ||
    EncAndDesMediaFileDestructorAddr === null ||
    EncAndDesMediaFileOpenAddr === null ||
    EncAndDesMediaFileGetSizeAddr === null ||
    EncAndDesMediaFileReadAddr === null) {
  throw new Error("部分导出函数未找到，请检查 QQMusicCommon.dll 版本");
}

console.log("[+] 所有导出函数地址验证通过");

// 构造函数
var EncAndDesMediaFileConstructor = new NativeFunction(
  EncAndDesMediaFileConstructorAddr, "pointer", ["pointer"], "thiscall"
);
var EncAndDesMediaFileDestructor = new NativeFunction(
  EncAndDesMediaFileDestructorAddr, "void", ["pointer"], "thiscall"
);
var EncAndDesMediaFileOpen = new NativeFunction(
  EncAndDesMediaFileOpenAddr, "bool", ["pointer", "pointer", "bool", "bool"], "thiscall"
);
var EncAndDesMediaFileGetSize = new NativeFunction(
  EncAndDesMediaFileGetSizeAddr, "uint32", ["pointer"], "thiscall"
);
var EncAndDesMediaFileRead = new NativeFunction(
  EncAndDesMediaFileReadAddr, "uint", ["pointer", "pointer", "uint32", "uint64"], "thiscall"
);

// Windows API: CreateDirectoryW
var kernel32 = Process.getModuleByName("kernel32.dll");
if (kernel32 === null) {
  throw new Error("无法找到 kernel32.dll");
}
var CreateDirectoryWAddr = kernel32.getExportByName("CreateDirectoryW");
if (CreateDirectoryWAddr === null) {
  throw new Error("无法找到 CreateDirectoryW 函数");
}
console.log("[+] CreateDirectoryW 地址: " + CreateDirectoryWAddr);
var CreateDirectoryW = new NativeFunction(
  CreateDirectoryWAddr,
  "bool", ["pointer", "pointer"]
);

console.log("[+] Hook 脚本初始化完成，等待调用...");

// 递归创建路径
function ensureDirRecursively(pathStr) {
  const parts = pathStr.split(/[\\/]/);
  let current = parts[0] === "" ? parts[0] + "\\" : parts[0];
  for (let i = 1; i < parts.length; i++) {
    current += "\\" + parts[i];
    const wide = Memory.allocUtf16String(current);
    CreateDirectoryW(wide, ptr(0));
  }
}

rpc.exports = {
  decrypt: function (srcFileName, tmpFileName) {
    // 构造对象
    var EncAndDesMediaFileObject = Memory.alloc(0x28);
    EncAndDesMediaFileConstructor(EncAndDesMediaFileObject);

    var fileNameUtf16 = Memory.allocUtf16String(srcFileName);
    var opened = EncAndDesMediaFileOpen(EncAndDesMediaFileObject, fileNameUtf16, 1, 0);
    if (!opened) {
      EncAndDesMediaFileDestructor(EncAndDesMediaFileObject);
      throw new Error("打开失败: " + srcFileName);
    }

    // 读取数据
    var fileSize = EncAndDesMediaFileGetSize(EncAndDesMediaFileObject);
    var buffer = Memory.alloc(fileSize);
    EncAndDesMediaFileRead(EncAndDesMediaFileObject, buffer, fileSize, 0);

    var data = buffer.readByteArray(fileSize);
    EncAndDesMediaFileDestructor(EncAndDesMediaFileObject);

    // 创建输出目录（递归）
    var lastSlash = tmpFileName.lastIndexOf("\\");
    if (lastSlash !== -1) {
      var dirPath = tmpFileName.substring(0, lastSlash);
      ensureDirRecursively(dirPath);
    }

    // 写入文件
    var tmpFile = new File(tmpFileName, "wb");
    tmpFile.write(data);
    tmpFile.flush();
    tmpFile.close();
  }
};
