# macOS 安装和常见提示

## 选择正确的版本

- Apple Silicon（M1 / M2 / M3 / M4 等）选择文件名含 `macos-arm64` 的 DMG 或 ZIP。
- Intel Mac 选择文件名含 `macos-x64` 的 DMG 或 ZIP。
- 在苹果菜单 → 关于本机，查看“芯片”或“处理器”。这两个包分别为原生架构，不是通用二进制包。要求 macOS 13 或更新版本。

从本项目 GitHub Release 下载。DMG 和 ZIP 内容为同一个应用，任选一种即可。

## 安装

1. 打开 DMG，将 `S7 Studio.app` 拖到同一窗口中的 `Applications`（应用程序）文件夹。安装完成后推出磁盘映像。
2. ZIP 用户先解压，再将 `S7 Studio.app` 拖到“应用程序”。不要直接在压缩包内运行。
3. 从“应用程序”打开 S7 Studio。当前版本采用 ad-hoc 签名，未使用 Apple Developer ID 签名或 Apple 公证，首次打开可能被 Gatekeeper 拦截。
4. 若提示“无法验证开发者”“Apple 无法检查是否包含恶意软件”，在尝试打开后进入“系统设置 → 隐私与安全性”，找到 S7 Studio，点击“仍要打开”，按提示确认。旧版系统也可能提供右键应用 → 打开。

这是 Apple 对未公证应用的处理流程，参见 [Apple 官方说明](https://support.apple.com/zh-cn/102445)。

## 提示“已损坏，无法打开，你应该将它移到废纸篓”

先点“取消”或“完成”，不要反复移动应用。这条提示不一定意味着文件真的损坏，也不能直接认定为下载隔离属性导致。

1. 确认包来自本项目 Release，并选择了正确架构。重新下载一次，排除下载和解压损坏。
2. 下载对应的 `.sha256` 文件，在终端切换到下载目录。例如 Apple Silicon DMG：

   ```bash
   cd ~/Downloads
   shasum -a 256 -c S7Studio-v0.1.0-macos-arm64.dmg.sha256
   ```

   应看到 `OK`。其他版本或 Intel 包请替换文件名。也可以对照 Release 的 `SHA256SUMS.txt`。校验不通过时删除下载包并重新下载，不要绕过检查。
3. 将应用完整复制到“应用程序”，检查签名完整性：

   ```bash
   codesign --verify --deep --strict "/Applications/S7 Studio.app"
   ```

   成功时通常没有输出；ad-hoc 签名验证成功不代表已经获得 Apple 公证。若报签名损坏或资源被修改，重新下载并安装，仍失败请提交 Issue。
4. 仅在确认来自本项目、SHA256 匹配且签名完整，仍因下载隔离被拦截时，运行以下命令，只清理本应用的下载隔离属性：

   ```bash
   xattr -dr com.apple.quarantine "/Applications/S7 Studio.app"
   open "/Applications/S7 Studio.app"
   ```

   如果应用安装在其他目录，请替换为实际 `.app` 路径。无需运行关闭全局 Gatekeeper 的命令。若系统明确报告恶意软件、撤销证书或企业策略禁止运行，请不要使用该步骤，应反馈给维护者或联系管理员。

## 更新与卸载

- 更新前退出应用，用新版本替换“应用程序”中的旧 `.app`。
- 卸载时退出应用，再将 `.app` 移到废纸篓。保存的 JSON 项目是独立文件，不会随应用删除；默认在文稿目录的 `S7 Studio` 文件夹，也可能是你在“项目保存设置”中选择的目录。
