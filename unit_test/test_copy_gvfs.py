import os
import tempfile
import pdfplumber
from unittest import TestCase, main
from unittest.mock import patch, MagicMock
from app_helper import ensure_local_copy 

class TestCopyGVFS(TestCase):

    def setUp(self):
        """ 測試前準備：建立一個模擬的 PDF 檔案 """
        self.test_dir = tempfile.gettempdir()
        self.test_pdf_path = os.path.join(self.test_dir, "test.pdf")

        # 建立一個假 PDF 檔案
        with open(self.test_pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n%Test PDF file\n")

        # 模擬一個 GVFS WebDAV 路徑
        self.mock_gvfs_path = f"/run/user/1000/gvfs/dav:host=nas.example.com,test.pdf"

    def tearDown(self):
        """ 測試後清理：刪除測試用的 PDF """
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

    @patch("subprocess.run")
    def test_ensure_local_copy_linux_gvfs(self, mock_subprocess):
        """ 測試 Linux GVFS: 應該使用 `gio copy` """
        mock_subprocess.return_value = MagicMock(returncode=0)

        with ensure_local_copy(self.mock_gvfs_path) as local_path:
            self.assertTrue(os.path.exists(local_path))  # 檔案應該成功複製
            with open(local_path, "rb") as f:
                self.assertTrue(f.read().startswith(b"%PDF-1.4"))  # 確保內容正確

        # with 區塊結束後，檔案應該被刪除
        self.assertFalse(os.path.exists(local_path))

    @patch("shutil.copy")
    def test_ensure_local_copy_non_gvfs(self, mock_shutil):
        """ 測試一般檔案 (非 GVFS): 應該使用 `shutil.copy` """
        mock_shutil.return_value = None  # 模擬 `shutil.copy` 成功

        with ensure_local_copy(self.test_pdf_path) as local_path:
            self.assertTrue(os.path.exists(local_path))  # 檔案應該成功複製
            with open(local_path, "rb") as f:
                self.assertTrue(f.read().startswith(b"%PDF-1.4"))  # 確保內容正確

        # with 區塊結束後，檔案應該被刪除
        self.assertFalse(os.path.exists(local_path))

    @patch("subprocess.run", side_effect=Exception("gio copy error"))
    def test_ensure_local_copy_linux_gvfs_fail(self, mock_subprocess):
        """ 測試 Linux GVFS 失敗情況: 應該拋出錯誤 """
        with self.assertRaises(Exception):
            with ensure_local_copy(self.mock_gvfs_path) as local_path:
                pass  # 這不應該被執行

    def test_pdfplumber_reads_copied_file(self):
        """ 測試 pdfplumber 是否能正確讀取複製的 PDF """
        with ensure_local_copy(self.test_pdf_path) as local_path:
            with pdfplumber.open(local_path) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else None
                self.assertIsNone(text)  # 測試文件是空的，但至少不應該報錯

if __name__ == "__main__":
    main()
