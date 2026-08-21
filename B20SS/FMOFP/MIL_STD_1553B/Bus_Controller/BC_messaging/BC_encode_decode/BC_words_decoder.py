####
#   Filename: BC_words_decoder.py
#
#   Class:      BC_decoders
#   Functions:      decode_command_word(self, word)
#                   decode_status_word(self, word)
#                   decode_data_word(self, word)
#
####

import json
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class BC_decoders:
    # Sync patterns according to MIL-STD-1553B
    COMMAND_SYNC = "100"  # Command word sync pattern
    DATA_SYNC = "001"     # Data word sync pattern
    message_error = ''
    instrumentation = ''
    service_request = ''
    reserved_bits = ''
    brdcst_received = ''
    busy = ''
    subsystem_flag = ''
    dynamic_bus_control_accpt = ''
    terminal_flag = ''
    RT_address = '' 
    
    def _parse_raw_data(self, raw_data):
        """Parse raw data from bytes/string format into list of binary strings."""
        try:
            # Convert bytes to string if needed
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode('ascii')
            
            # If it's a string representation of a list, parse it
            if raw_data.startswith('[') and raw_data.endswith(']'):
                # Use json.loads for safe parsing of string representation of list
                return json.loads(raw_data)
            
            # If it's a single word, return as single-item list
            return [raw_data]
        except Exception as e:
            logger.error(f"Error parsing raw data: {str(e)}")
            logger.error(f"Raw data: {raw_data}")
            raise

    def decode_command_word(self, word):
        """
        Decode a command word according to MIL-STD-1553B specification.
        Command word format:
        - Sync (3 bits): 100
        - RT Address (5 bits)
        - T/R bit (1 bit)
        - Subaddress/Mode (5 bits)
        - Word Count/Mode Code (5 bits)
        - Parity (1 bit)
        """
        try:
            # Parse raw data into list of words
            words = self._parse_raw_data(word)
            
            # Use first word for command word
            command_word = words[0]

            # Validate word length
            if len(command_word) != 20:
                raise ValueError(f"Command word must be 20 bits, got {len(command_word)}")

            # Extract and validate sync bits
            sync_bits = command_word[:3]
            if sync_bits != self.COMMAND_SYNC:
                raise ValueError(f"Invalid command word sync bits: {sync_bits}")

            # Extract other fields
            rt_address = command_word[3:8]
            tr_bit = command_word[8]
            subaddress_mode = command_word[9:14]
            word_count_mode = command_word[14:19]
            parity = command_word[19]

            # Validate parity
            if not self._validate_parity(command_word):
                raise ValueError("Parity check failed")

            return {
                'sync': sync_bits,
                'rt_address': int(rt_address, 2),
                'tr_bit': int(tr_bit),
                'subaddress_mode': int(subaddress_mode, 2),
                'word_count_mode': int(word_count_mode, 2),
                'parity': int(parity)
            }

        except Exception as e:
            logger.error(f"Error parsing command word: {str(e)}")
            logger.error(f"Raw received data: {word}")
            raise

    def _validate_parity(self, word):
        """
        Validate odd parity for the word.
        Returns True if parity is valid, False otherwise.
        """
        # Count number of 1s in the word (excluding parity bit)
        ones_count = word[:19].count('1')
        parity_bit = int(word[19])
        
        # For odd parity, total number of 1s including parity bit should be odd
        return (ones_count + parity_bit) % 2 == 1

    def decode_status_word(self, word):
        """
        Decode a status word according to MIL-STD-1553B specification.
        Status word format:
        - Sync (3 bits): 100
        - RT Address (5 bits)
        - Message Error (1 bit)
        - Instrumentation (1 bit)
        - Service Request (1 bit)
        - Reserved (3 bits)
        - Broadcast Command (1 bit)
        - Busy (1 bit)
        - Subsystem Flag (1 bit)
        - Dynamic Bus Control (1 bit)
        - Terminal Flag (1 bit)
        - Parity (1 bit)
        """
        try:
            # Parse raw data into list of words
            words = self._parse_raw_data(word)
            
            # Use first word for status word
            status_word = words[0]

            # Validate word length
            if len(status_word) != 20:
                raise ValueError(f"Status word must be 20 bits, got {len(status_word)}")

            # Extract and validate sync bits
            sync_bits = status_word[:3]
            if sync_bits != self.COMMAND_SYNC:  # Status words use same sync as command words
                raise ValueError(f"Invalid status word sync bits: {sync_bits}")

            # Extract fields
            rt_address = status_word[3:8]
            message_error = status_word[8]
            instrumentation = status_word[9]
            service_request = status_word[10]
            reserved = status_word[11:14]
            broadcast_cmd = status_word[14]
            busy = status_word[15]
            subsystem_flag = status_word[16]
            dynamic_bus_control = status_word[17]
            terminal_flag = status_word[18]
            parity = status_word[19]

            # Validate parity
            if not self._validate_parity(status_word):
                raise ValueError("Parity check failed")

            return {
                'sync': sync_bits,
                'rt_address': int(rt_address, 2),
                'message_error': int(message_error),
                'instrumentation': int(instrumentation),
                'service_request': int(service_request),
                'reserved': int(reserved, 2),
                'broadcast_cmd': int(broadcast_cmd),
                'busy': int(busy),
                'subsystem_flag': int(subsystem_flag),
                'dynamic_bus_control': int(dynamic_bus_control),
                'terminal_flag': int(terminal_flag),
                'parity': int(parity)
            }

        except Exception as e:
            logger.error(f"Error parsing status word: {str(e)}")
            logger.error(f"Raw received data: {word}")
            raise

    def decode_data_word(self, word):
        """
        Decode a data word according to MIL-STD-1553B specification.
        Data word format:
        - Sync (3 bits): 001
        - Data (16 bits)
        - Parity (1 bit)
        """
        try:
            # Parse raw data into list of words
            words = self._parse_raw_data(word)
            
            # Use second word for data word if available, otherwise first word
            data_word = words[1] if len(words) > 1 else words[0]

            # Validate word length
            if len(data_word) != 20:
                raise ValueError(f"Data word must be 20 bits, got {len(data_word)}")

            # Extract and validate sync bits
            sync_bits = data_word[:3]
            if sync_bits != self.DATA_SYNC:
                raise ValueError(f"Invalid data word sync bits: {sync_bits}")

            # Extract data and parity
            data = data_word[3:19]
            parity = data_word[19]

            # Validate parity
            if not self._validate_parity(data_word):
                raise ValueError("Parity check failed")

            return {
                'sync': sync_bits,
                'data': int(data, 2),
                'parity': int(parity)
            }

        except Exception as e:
            logger.error(f"Error parsing data word: {str(e)}")
            logger.error(f"Raw received data: {word}")
            raise

    # NOTE: a second, byte-for-byte identical _validate_parity() used to be
    # defined here, silently shadowing the one already defined above (same
    # bug pattern as BC_error_checkers' wrong-parity duplicate check_parity/
    # check_character fixed earlier this session). Unlike that one, both
    # copies here were functionally identical, so there was no behavioral
    # bug -- just dead, redundant code. Removed rather than kept, since a
    # future edit to one copy without the other would silently reintroduce
    # a real bug (production readiness deep dive, found via a repo-wide
    # duplicate-method scan).
