############################################################################################################################
#
#   Warning:
#   This script will delete all __pycache__ folders and their contents from the
#   specified directory AND all subdirectories, all log files, all text files, and all database files.
#   Use with caution.
#
#   Usage:
#   Run in debug mode and pass the path to the directory you want to clean up
#
############################################################################################################################
import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
B20SS_path = os.path.join(project_root, '')
sys.path.insert(0, B20SS_path)
import FMOFP.Utils.common.fetching as fetching
import logging
logger = logging


def delete_pycache(path):
    for root, dirs, files in os.walk(path):
        for dir in dirs:
            if dir == '__pycache__':
                pycache_path = os.path.join(root, dir)
                logger.info(f"Deleting {pycache_path}")
                try:
                    for item in os.listdir(pycache_path):
                        item_path = os.path.join(pycache_path, item)
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            delete_pycache(item_path)
                    os.rmdir(pycache_path)
                except Exception as e:
                    logger.info(f"Error deleting {pycache_path}: {e}")
        for file in files:
            if file.endswith('.pyc'):
                pyc_file_path = os.path.join(root, file)
                logger.info(f"Deleting {pyc_file_path}")
                try:
                    os.remove(pyc_file_path)
                except Exception as e:
                    logger.info(f"Error deleting {pyc_file_path}: {e}")

def delete_log_files(path):
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith('.log'):
                log_file_path = os.path.join(root, file)
                logger.info(f"Deleting {log_file_path}")
                try:
                    os.remove(log_file_path)
                except Exception as e:
                    logger.info(f"Error deleting {log_file_path}: {e}")

def delete_txt_files(path):
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith('.txt'):
                txt_file_path = os.path.join(root, file)
                logger.info(f"Deleting {txt_file_path}")
                try:
                    os.remove(txt_file_path)
                except Exception as e:
                    logger.info(f"Error deleting {txt_file_path}: {e}")

def delete_db_files(path):
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith('.db'):
                db_file_path = os.path.join(root, file)
                logger.info(f"Deleting {db_file_path}")
                try:
                    os.remove(db_file_path)
                except Exception as e:
                    logger.info(f"Error deleting {db_file_path}: {e}")

def main(path):
    delete_pycache(path)
    delete_log_files(path)
    delete_txt_files(path)
    delete_db_files(path)

if __name__ == "__main__":

    if os.path.exists(B20SS_path):
        main(B20SS_path)
    else:
        logger.info(f"The path {B20SS_path} does not exist.")