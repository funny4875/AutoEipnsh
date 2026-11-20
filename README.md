# eipnsh主計系統小幫手 v1.0.0

Windows Python 桌面程式，參考 ClickPilot 的 Selenium／ChromeDriver 與附檔欄位。可管理多位使用者及學校代碼，選擇後開啟 Chrome 並填入資料。請確認學校，手動輸入驗證碼並登入。

## 執行

需安裝 Windows、Python 3.10 以上及 Google Chrome。解壓縮後在本資料夾開啟 PowerShell：

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

Selenium Manager 首次執行時可能需要網路下載相容的 ChromeDriver。程式以 ddddocr 辨識驗證碼並填入，等待 1 秒後按登入；辨識失敗時可手動輸入並登入。辨識結果可能有誤，請查看網站回應。舊版使用者請編輯並補上學校代碼。

帳密以 Windows DPAPI 加密，存放在目前使用者的 `%LOCALAPPDATA%\AccountingLogin\accounts.json`，通常只能由同一台電腦、同一 Windows 使用者帳戶解密。請備份原始密碼；移轉帳戶或重灌系統可能無法還原。附檔中的帳密不包含於程式中。

