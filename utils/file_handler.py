import os
import hashlib
from utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader

def get_file_md5_hex(filepath: str):    # 获取文件的md5

    if not os.path.exists(filepath):
        logger.error(f"[md5计算]文件{filepath}不存在")
        return

    if not os.path.isfile(filepath):
        logger.error(f"[md5计算]路径{filepath}不是文件")
        return

    md5_obj = hashlib.md5()

    chunk_size = 4096
    try:
        with open(filepath, 'rb') as f: # 必须二进制读取
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)
                """
                := 是一个pythond3.8新特性

                赋值运算符，将右边表达式的结果赋给左边变量
                这段代码等价于：
                chunk = f.read(chunk_size)
                while chunk:
                    md5_obj.update(chunk)
                    chunk = f.read(chunk_size)
                """
            md5_hex = md5_obj.hexdigest()
            return md5_hex
        
    except Exception as e:
        logger.error(f"[md5计算]文件{filepath}读取错误:{str(e)}")
        return None

# 获取文件的md5的十六进制字符串

def listdir_with_allowed_type(path: str, allowed_types: tuple[str]):    # 返回文件夹内的文件列表(允许的文件后缀)
    files = []

    if not os.path.isdir(path): 
        logger.error(f"[listdir_with_allowed_type]参数path:{path}不是文件夹]")
        return allowed_types
    
    for f in os.listdir(path):
        if f.endswith(allowed_types):
            files.append(os.path.join(path, f))

    return tuple(files)

def pdf_loader (filepath: str, password=None) -> list[Document]:
    return PyPDFLoader(filepath, password).load()
    

def txt_loader (filepath: str) -> list[Document]:
    return TextLoader(filepath,encoding="utf-8").load()