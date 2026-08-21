"""
Process MIL-STD-1553B block transfer messages.

Handles block transfer protocol between RT and BC.
"""
import time
import logging
import traceback
import asyncio
from typing import Dict, Any, Optional, List

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.block_transfer_manager import get_block_transfer_manager
from FMOFP.MIL_STD_1553B.Bus_Controller.bc_message_extractor import get_bc_message_extractor

logger = get_logger()

async def handle_transfer_init(extracted_fields: Dict[str, Any], bc_instance) -> bool:
    """
    Handle block transfer initialization from RT.
    
    Args:
        extracted_fields: Dictionary of extracted message fields
        bc_instance: Bus_Controller instance for access to methods
        
    Returns:
        bool: True if successfully processed
    """
    try:
        request_id = extracted_fields.get('request_id')
        if not request_id:
            logger.error("[BC_BLOCK] Missing request_id for block transfer initialization")
            return False
            
        logger.info(f"[BC_BLOCK] Processing block transfer initialization from RT for request_id: {request_id}")
        
        # Clear any existing transfer data for this request_id
        transfer_manager = get_block_transfer_manager()
        transfer_manager.clear_transfer(request_id)
        
        # Extract total sequences and other metadata if available
        total_sequences = extracted_fields.get('total_sequences', 1)
        metadata = extracted_fields.get('metadata', {})
        if isinstance(metadata, dict):
            total_sequences = metadata.get('total_sequences', total_sequences)
        
        logger.info(f"[BC_BLOCK] Block transfer initialization from RT: request_id={request_id}, total_sequences={total_sequences}")
        return True
    except Exception as e:
        logger.error(f"[BC_BLOCK] Error in handle_transfer_init: {e}")
        logger.error(traceback.format_exc())
        return False

async def handle_transfer_data(extracted_fields: Dict[str, Any], bc_instance) -> bool:
    """
    Handle block transfer data message from RT.
    
    Args:
        extracted_fields: Dictionary of extracted message fields
        bc_instance: Bus_Controller instance for access to methods
        
    Returns:
        bool: True if successfully processed
    """
    try:
        request_id = extracted_fields.get('request_id')
        if not request_id:
            logger.error("[BC_BLOCK] Missing request_id for block transfer data")
            return False
        
        # Extract required block transfer parameters
        sequence_number = extracted_fields.get('sequence_number', 1)
        total_sequences = extracted_fields.get('total_sequences', 1)
        is_final = extracted_fields.get('is_final', False)
        
        # Extract the same fields from metadata if available and not already present
        metadata = extracted_fields.get('metadata', {})
        if isinstance(metadata, dict):
            if 'sequence_number' in metadata and not extracted_fields.get('sequence_number'):
                sequence_number = metadata.get('sequence_number')
            if 'total_sequences' in metadata and not extracted_fields.get('total_sequences'):
                total_sequences = metadata.get('total_sequences')
            if 'is_final' in metadata and not extracted_fields.get('is_final'):
                is_final = metadata.get('is_final')
        
        # Extract data
        data_array = extracted_fields.get('data', [])
        
        # Register this block with the transfer manager
        transfer_manager = get_block_transfer_manager()
        logger.info(f"[BC_BLOCK] Registering block {sequence_number}/{total_sequences} for request_id: {request_id}")
        transfer_complete = transfer_manager.register_block(
            request_id, 
            sequence_number, 
            total_sequences, 
            is_final, 
            data_array
        )
        
        # Get and log transfer status safely
        status = transfer_manager.get_transfer_status(request_id)
        
        # Safely log transfer status with null-safe access
        received_blocks = status.get('received_blocks', 0)
        total_blocks = status.get('total_blocks', 0)
        percent_complete = status.get('percent_complete', 0.0)
        
        logger.info(f"[BC_BLOCK] Transfer status: {received_blocks}/{total_blocks} blocks received ({percent_complete:.1f}% complete)")
        
        # For in-progress transfers, acknowledge receipt but don't route
        if not transfer_complete:
            logger.info(f"[BC_BLOCK] Block transfer in progress from RT for request_id: {request_id}")
            return True
        else:
            # The transfer is complete - process the full data
            assembled_data = transfer_manager.get_assembled_data(request_id)
            
            if assembled_data and len(assembled_data) > 0:
                logger.info(f"[BC_BLOCK] Processing complete block transfer from RT with {len(assembled_data)} data points")
                # Return the assembled data to the caller
                extracted_fields['data'] = assembled_data
                extracted_fields['block_transfer_complete'] = True
                extracted_fields['binary_data_length'] = len(assembled_data)
                logger.info(f"[BC_BLOCK] Successfully retrieved and assembled complete block transfer data")
                return True
            else:
                logger.error(f"[BC_BLOCK] Failed to get assembled data for block transfer from RT despite transfer being complete")
                return False
    except Exception as e:
        logger.error(f"[BC_BLOCK] Error in handle_transfer_data: {e}")
        logger.error(traceback.format_exc())
        return False

async def handle_transfer_complete(extracted_fields: Dict[str, Any], bc_instance) -> bool:
    """
    Handle block transfer completion from RT.
    
    Args:
        extracted_fields: Dictionary of extracted message fields
        bc_instance: Bus_Controller instance for access to methods
        
    Returns:
        bool: True if successfully processed
    """
    try:
        request_id = extracted_fields.get('request_id')
        if not request_id:
            logger.error("[BC_BLOCK] Missing request_id for block transfer completion")
            return False
            
        logger.info(f"[BC_BLOCK] Block transfer complete message received for request_id: {request_id}")
        
        # Process final data if available
        transfer_manager = get_block_transfer_manager()
        if transfer_manager.is_transfer_complete(request_id):
            assembled_data = transfer_manager.get_assembled_data(request_id)
            if assembled_data:
                extracted_fields['data'] = assembled_data
                extracted_fields['block_transfer_complete'] = True
                extracted_fields['binary_data_length'] = len(assembled_data)
                logger.info(f"[BC_BLOCK] Successfully retrieved assembled data for completed transfer")
                return True
            else:
                logger.warning(f"[BC_BLOCK] Transfer marked complete but no assembled data returned")
                return False
        else:
            logger.warning(f"[BC_BLOCK] Received transfer complete but transfer is not complete in manager")
            return False
    except Exception as e:
        logger.error(f"[BC_BLOCK] Error in handle_transfer_complete: {e}")
        logger.error(traceback.format_exc())
        return False

def detect_block_transfer(extracted_fields: Dict[str, Any]) -> str:
    """
    Determine if this is a block transfer message and what type.
    
    Args:
        extracted_fields: Dictionary of extracted message fields
        
    Returns:
        str: 'init', 'data', 'complete', or None if not a block transfer
    """
    # Check explicit flags first (top level)
    if extracted_fields.get('is_transfer_init', False):
        return 'init'
    if extracted_fields.get('is_transfer_data', False):
        return 'data'
    if extracted_fields.get('is_transfer_complete', False):
        return 'complete'
        
    # Check for flags in metadata
    metadata = extracted_fields.get('metadata', {})
    if isinstance(metadata, dict):
        if metadata.get('is_transfer_init', False):
            return 'init'
        if metadata.get('is_transfer_data', False):
            return 'data'
        if metadata.get('is_transfer_complete', False):
            return 'complete'
    
    # Check for sequence info that suggests a block transfer
    if extracted_fields.get('sequence_number') is not None and extracted_fields.get('total_sequences') is not None:
        return 'data'
    
    return None
