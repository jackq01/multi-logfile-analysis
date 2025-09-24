import sys
import logging
from PyQt5.QtWidgets import QApplication
from app.main_window import LogAnalyzerApp

# 初始化日志记录器
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("log_analyzer_debug.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LogAnalyzerApp()
    window.show()
    sys.exit(app.exec_())
