# S7 Studio v@VERSION@

@CHANGES@

## 下载哪个文件

- **Apple Silicon Mac（M 系列）**：`S7Studio-v@VERSION@-macos-arm64.dmg`；也可下载同名前缀的 `.zip`。
- **Intel Mac**：`S7Studio-v@VERSION@-macos-x64.dmg`；也可下载同名前缀的 `.zip`。
- **Windows 10 / 11 x64 安装版**：`S7Studio-v@VERSION@-windows-x64-setup.exe`，双击后按向导安装。安装到当前用户目录，无需管理员权限。
- **Windows 便携版**：`S7Studio-v@VERSION@-windows-x64.zip`，完整解压后运行 `S7 Studio/S7 Studio.exe`；必须保留 `_internal` 等同目录文件，不能只复制 EXE。

Mac 要求 macOS 14 或更新版本。请通过“苹果菜单 → 关于本机”确认芯片。GitHub 自动附带的 `Source code` 是源码包，不是安装包。

## Mac 安装与首次打开

1. 打开 DMG，把 `S7 Studio.app` 拖到 `Applications`，完成后推出磁盘映像；ZIP 用户先解压，再把 `.app` 拖到“应用程序”。
2. 从“应用程序”启动。目前包采用 ad-hoc 签名，**未使用 Apple Developer ID 签名或 Apple 公证**。
3. 若提示“无法验证开发者”“Apple 无法检查是否包含恶意软件”，先尝试打开一次，再到“系统设置 → 隐私与安全性”，找到 S7 Studio，点击“仍要打开”。参考 [Apple 官方说明](https://support.apple.com/zh-cn/102445)。

### 提示“已损坏，无法打开，你应该将它移到废纸篓”怎么办

先点“取消”或“完成”。确认文件来自本 Release、架构正确，并重新下载排除损坏。下载对应 `.sha256` 文件后，在终端检查完整性，例如：

```bash
cd ~/Downloads
shasum -a 256 -c S7Studio-v@VERSION@-macos-arm64.dmg.sha256
```

应看到 `OK`；Intel 或 ZIP 用户替换为对应文件名。再将应用完整复制到“应用程序”，检查签名完整性：

```bash
codesign --verify --deep --strict "/Applications/S7 Studio.app"
```

签名验证成功通常不输出内容，不代表已公证。**校验失败、签名损坏或文件被修改时，请重新下载，不要绕过检查。**

仅在确认是可信且完整的本项目应用，仍因下载隔离属性被拦截时，运行：

```bash
xattr -dr com.apple.quarantine "/Applications/S7 Studio.app"
open "/Applications/S7 Studio.app"
```

命令仅针对 S7 Studio；若安装路径不同，请替换实际路径。无需关闭系统全局安全检查。明确提示恶意软件、撤销证书或企业策略阻止时，不应绕过，应反馈维护者或联系管理员。

完整安装说明：[macOS 安装与常见提示](https://github.com/WendelYu/S7Simulator/blob/v@VERSION@/docs/MAC_INSTALL.md)。

## Windows 与完整性

Windows 程序尚未配置 Authenticode 签名。若 SmartScreen 提示无法识别应用，先核对下载来源和 SHA256，仅在确认信任后选择“更多信息 → 仍要运行”。无需关闭 Defender；企业策略阻止时联系管理员。

使用 PowerShell 检查下载文件，与 `SHA256SUMS.txt` 对照：

```powershell
Get-FileHash .\S7Studio-v@VERSION@-windows-x64-setup.exe -Algorithm SHA256
```

升级前退出程序，再运行安装包。卸载通过系统“已安装的应用”；Mac 卸载将 `.app` 移到废纸篓。项目 JSON 独立保存在用户选择的目录，更新或卸载不会主动删除项目。

所有附件由同一版本标签的 GitHub Actions 测试、构建并完成启动检查后发布，含每个包的 `.sha256` 及汇总 `SHA256SUMS.txt`。
