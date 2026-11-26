import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import threading
import time
import sys
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk

from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL = 'https://eipnsh.k12ea.gov.tw/'
VERSION = '1.0.2'
RELEASE = 'https://github.com/funny4875/AutoEipnsh/releases/latest'


def dialog(method, title, *args, **kwargs):
    return getattr(messagebox, method)(title + ' v' + VERSION, *args, **kwargs)
DATA = Path(os.environ['LOCALAPPDATA']) / 'AccountingLogin' / 'accounts.json'


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]


def protect(value, decrypt=False):
    raw = base64.b64decode(value) if decrypt else value.encode('utf-8')
    buffer = ctypes.create_string_buffer(raw, len(raw))
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    result = Blob()
    crypt = ctypes.windll.crypt32
    if decrypt:
        ok = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result))
    else:
        ok = crypt.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result))
    if not ok:
        raise ctypes.WinError()
    try:
        output = ctypes.string_at(result.data, result.size)
    finally:
        ctypes.windll.kernel32.LocalFree(result.data)
    return output.decode('utf-8') if decrypt else base64.b64encode(output).decode('ascii')


class App:
    def __init__(self, root):
        self.root = root
        self.driver = None
        self.items = []
        self.editing = None
        root.title('eipnsh主計系統小幫手 v' + VERSION)
        icon = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'icon.ico'
        if icon.exists():
            root.iconbitmap(str(icon))
        root.geometry('480x480')
        frame = ttk.Frame(root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='eipnsh主計系統小幫手 v' + VERSION, font=('Microsoft JhengHei', 16, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='選擇使用者後開啟 Chrome 並填入登入資料。').pack(anchor='w', pady=8)
        self.select = ttk.Combobox(frame, state='readonly')
        self.select.pack(fill='x')
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=8)
        ttk.Button(buttons, text='開啟並填入帳密', command=self.login).pack(side='left')
        ttk.Button(buttons, text='編輯', command=self.edit).pack(side='left', padx=5)
        ttk.Button(buttons, text='刪除', command=self.delete).pack(side='left')
        ttk.Separator(frame).pack(fill='x', pady=10)
        self.heading = ttk.Label(frame, text='新增使用者')
        self.heading.pack(anchor='w')
        form = ttk.Frame(frame)
        form.pack(fill='x')
        self.fields = {}
        for row, (label, name) in enumerate([('顯示名稱', 'label'), ('學校代碼', 'school'), ('帳號', 'username'), ('密碼', 'password')]):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', pady=5)
            entry = ttk.Entry(form, show='●' if name == 'password' else '')
            entry.grid(row=row, column=1, sticky='ew', padx=10)
            self.fields[name] = entry
        form.columnconfigure(1, weight=1)
        actions = ttk.Frame(frame)
        actions.pack(anchor='w', pady=10)
        ttk.Button(actions, text='儲存', command=self.save).pack(side='left')
        ttk.Button(actions, text='清除', command=self.clear).pack(side='left', padx=6)
        self.status = tk.StringVar(value='帳密由 Windows 使用者帳戶加密保護。')
        ttk.Label(frame, textvariable=self.status, wraplength=430).pack(anchor='w', pady=8)
        self.load()
        threading.Thread(target=self.check_updates, daemon=True).start()

    def check_updates(self):
        try:
            request = urllib.request.Request('https://api.github.com/repos/funny4875/AutoEipnsh/releases/latest', headers={'User-Agent': 'AutoEipnsh'})
            with urllib.request.urlopen(request, timeout=6) as response:
                release = json.load(response)
            tag = release.get('tag_name', '').lstrip('v')
            if not all(part.isdigit() for part in tag.split('.')):
                return
            if tuple(map(int, tag.split('.'))) > tuple(map(int, VERSION.split('.'))):
                self.root.after(0, self.offer_update, tag)
        except Exception:
            pass

    def offer_update(self, tag):
        if messagebox.askyesno('更新通知 v' + VERSION, '發現新版本 v' + tag + '，要開啟下載頁面嗎？', parent=self.root):
            webbrowser.open(RELEASE)

    def load(self):
        if DATA.exists():
            try:
                self.items = json.loads(protect(DATA.read_text(encoding='utf-8'), True))
            except Exception:
                dialog('showerror', '讀取失敗', '無法解密帳號資料。請確認使用原本儲存資料的 Windows 使用者帳戶。')
                self.root.destroy()
                return
        self.refresh()

    def refresh(self):
        self.select['values'] = [item['label'] + '（' + item['username'] + '）' for item in self.items]
        if self.items:
            self.select.current(0)
        else:
            self.select.set('')

    def write(self, items):
        DATA.parent.mkdir(parents=True, exist_ok=True)
        temporary = DATA.with_suffix('.tmp')
        temporary.write_text(protect(json.dumps(items, ensure_ascii=False)), encoding='utf-8')
        os.replace(temporary, DATA)
        self.items = items
        self.refresh()

    def clear(self):
        self.editing = None
        self.heading.config(text='新增使用者')
        for entry in self.fields.values():
            entry.delete(0, 'end')

    def save(self):
        item = {name: field.get().strip() if name != 'password' else field.get() for name, field in self.fields.items()}
        if not all(item.values()):
            dialog('showwarning', '資料不完整', '請填寫顯示名稱、學校代碼、帳號和密碼。')
            return
        items = list(self.items)
        if self.editing is None:
            items.append(item)
        else:
            items[self.editing] = item
        try:
            self.write(items)
            self.clear()
            self.status.set('使用者已儲存。')
        except Exception as exc:
            dialog('showerror', '儲存失敗', str(exc))

    def edit(self):
        index = self.select.current()
        if index < 0:
            return
        self.clear()
        self.editing = index
        self.heading.config(text='編輯使用者')
        for name, entry in self.fields.items():
            entry.insert(0, self.items[index].get(name, ''))

    def delete(self):
        index = self.select.current()
        if index < 0 or not dialog('askyesno', '刪除', '確定刪除這位使用者？'):
            return
        try:
            self.write([item for i, item in enumerate(self.items) if i != index])
            self.clear()
        except Exception as exc:
            dialog('showerror', '刪除失敗', str(exc))

    def login(self):
        index = self.select.current()
        if index < 0:
            dialog('showwarning', '請選擇使用者', '請先新增並選擇使用者。')
            return
        item = self.items[index].copy()
        if not item.get('school'):
            dialog('showwarning', '缺少學校代碼', '請先編輯使用者並填寫學校代碼。')
            return
        self.status.set('正在開啟 Chrome，請稍候……')
        threading.Thread(target=self.open_browser, args=(item,), daemon=True).start()

    def open_browser(self, item):
        try:
            if self.driver is None:
                self.driver = ChromeDriver()
            self.driver.get(URL)
            wait = WebDriverWait(self.driver, 20)
            school = wait.until(EC.element_to_be_clickable((By.ID, 'SchoolName')))
            school.click()
            school.clear()
            school.send_keys(item['school'])
            school.send_keys(Keys.ENTER)
            user = wait.until(EC.visibility_of_element_located((By.ID, 'User')))
            password = self.driver.find_element(By.ID, 'Pass')
            user.clear()
            user.send_keys(item['username'])
            password.clear()
            password.send_keys(item['password'])
            try:
                import ddddocr
                image = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#Main img[alt*="驗證碼"]')))
                result = ddddocr.DdddOcr(show_ad=False).classification(image.screenshot_as_png).strip()
                if not result:
                    raise ValueError('未辨識出文字')
                captcha = self.driver.find_element(By.ID, 'Captcha')
                captcha.clear()
                captcha.send_keys(result)
                self.root.after(0, self.status.set, '已填入資料，等待 1 秒後登入……')
                time.sleep(1)
                wait.until(EC.element_to_be_clickable((By.ID, 'Send'))).click()
                self.root.after(0, self.status.set, '已按下登入，等待登入成功……')
            except Exception:
                self.root.after(0, self.status.set, '驗證碼辨識或登入操作失敗，請手動完成登入。')
            try:
                button = WebDriverWait(self.driver, 300).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="APY"]/div/span[1]'))
                )
                button.click()
                self.root.after(0, self.status.set, '登入成功，已點選指定按鈕。')
            except Exception:
                self.root.after(0, self.status.set, '等待登入或點選按鈕逾時，請查看網頁並手動操作。')
        except Exception as exc:
            self.driver = None
            detail = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            self.root.after(0, self.status.set, '開啟或填入失敗：' + detail)


if __name__ == '__main__':
    window = tk.Tk()
    app = App(window)
    window.mainloop()
