from Utils.logger.sys_logger import get_logger


logger = get_logger()

class RTWordsDecoder:
    # Sync patterns according to MIL-STD-1553B (matching BC_msg.py)
    COMMAND_SYNC = "100"  # Command word sync pattern
    DATA_SYNC = "001"     # Data word sync pattern
    STATUS_SYNC = "100"   # Status word sync pattern

    def decode_command_word(self, word):
        """
        Decode a command word according to MIL-STD-1553B specification.
        Command word format (20 bits):
        - Sync (3 bits): 100
        - RT Address (5 bits)
        - T/R bit (1 bit)
        - Subaddress/Mode (5 bits)
        - Word Count/Mode Code (5 bits)
        - P bit (1 bit)
        """
        try:
            # Convert from bytes if necessary
            if isinstance(word, bytes):
                word = word.decode('ascii')
            
            # Remove any list formatting if present
            word = word.strip("[]'")

            # Validate word length
            if len(word) != 20:
                raise ValueError(f"Command word must be 20 bits, got {len(word)}")

            # Extract and validate sync bits
            sync_bits = word[:3]
            if sync_bits != self.COMMAND_SYNC:
                raise ValueError(f"Invalid command word sync bits: {sync_bits}")

            # Extract other fields
            rt_address = word[3:8]
            tr_bit = word[8]
            subaddress_mode = word[9:14]
            word_count_mode = word[14:19]
            parity = word[19]

            # Validate parity
            if not self._validate_parity(word):
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

    def decode_status_word(self, word):
        """
        Decode a status word according to MIL-STD-1553B specification.
        Status word format (20 bits):
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
        - P bit (1 bit)
        """
        try:
            # Convert from bytes if necessary
            if isinstance(word, bytes):
                word = word.decode('ascii')
            
            # Remove any list formatting if present
            word = word.strip("[]'")

            # Validate word length
            if len(word) != 20:
                raise ValueError(f"Status word must be 20 bits, got {len(word)}")

            # Extract and validate sync bits
            sync_bits = word[:3]
            if sync_bits != self.STATUS_SYNC:
                raise ValueError(f"Invalid status word sync bits: {sync_bits}")

            # Extract fields
            rt_address = word[3:8]
            message_error = word[8]
            instrumentation = word[9]
            service_request = word[10]
            reserved = word[11:14]
            broadcast_cmd = word[14]
            busy = word[15]
            subsystem_flag = word[16]
            dynamic_bus_control = word[17]
            terminal_flag = word[18]
            parity = word[19]

            # Validate parity
            if not self._validate_parity(word):
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
        Data word format (20 bits):
        - Sync (3 bits): 001
        - Data (16 bits)
        - P bit (1 bit)
        """
        try:
            # Convert from bytes if necessary
            if isinstance(word, bytes):
                word = word.decode('ascii')
            
            # Remove any list formatting if present
            word = word.strip("[]'")

            # Validate word length
            if len(word) != 20:
                raise ValueError(f"Data word must be 20 bits, got {len(word)}")

            # Extract and validate sync bits
            sync_bits = word[:3]
            if sync_bits != self.DATA_SYNC:
                raise ValueError(f"Invalid data word sync bits: {sync_bits}")

            # Extract data and parity
            data = word[3:19]
            parity = word[19]

            # Validate parity
            if not self._validate_parity(word):
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
