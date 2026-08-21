import os
import sys
from FMOFP.Utils.logger.sys_logger import get_logger
logger = get_logger()

def setup_environment():
    # Get the absolute path to the project root (B20SS directory)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    # Add project root to Python path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # logger.info current Python path for debugging
    logger.info("Python path:")
    for p in sys.path:
        logger.info(f"  {p}")

if __name__ == "__main__":
    setup_environment()
