from Utils.logger.sys_logger import get_logger

logger = get_logger()

class RTWordsEncoder:
    # Sync patterns according to MIL-STD-1553B
    STATUS_SYNC = "100"  # Status word sync pattern (same as command word)
    DATA_SYNC = "001"    # Data word sync pattern

    def encode_status_word(self, rt_address, message_error=0, instrumentation=0,
                          service_request=0, broadcast_cmd=0, busy=0,
                          subsystem_flag=0, dynamic_bus_control=0, terminal_flag=1):
        """
        Encode a status word according to MIL-STD-1553B specification.
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
            # Validate RT address
            if isinstance(rt_address, str):
                if len(rt_address) != 5 or not rt_address.isdigit():
                    raise ValueError("RT address invalid length or format")
                rt_addr = int(rt_address, 2)
            else:
                rt_addr = rt_address

            if not (0 <= rt_addr <= 31):
                raise ValueError(f"RT address must be between 0 and 31, got {rt_addr}")

            # Start with sync bits (100)
            word = self.STATUS_SYNC

            # Add RT address (5 bits)
            word += format(rt_addr, '05b')

            # Add status bits according to MIL-STD-1553B spec
            word += str(message_error)  # Message Error
            word += str(instrumentation)  # Instrumentation
            word += str(service_request)  # Service Request
            word += '000'  # Reserved bits
            word += str(broadcast_cmd)  # Broadcast Command
            word += str(busy)  # Busy
            word += str(subsystem_flag)  # Subsystem Flag
            word += str(dynamic_bus_control)  # Dynamic Bus Control (default 0)
            word += str(terminal_flag)  # Terminal Flag (default 1)

            # Calculate and add parity bit
            parity = self._calculate_parity(word)
            word += str(parity)

            # Verify final length
            if len(word) != 20:
                raise ValueError(f"Invalid word length: {len(word)} bits")

            logger.debug(f"Built status word: {word}")
            return word

        except Exception as error:
            logger.error("Remote Terminal Error while encoding a status word.")
            logger.error(str(error))
            raise

    def encode_data_word(self, data):
        """
        Encode a data word according to MIL-STD-1553B specification.
        Data word format (20 bits):
        - Sync (3 bits): 001
        - Data (16 bits)
        - P bit (1 bit)
        """
        try:
            # Validate data range (16 bits max)
            if isinstance(data, str):
                if len(data) != 16 or not all(c in '01' for c in data):
                    raise ValueError("Invalid data word format")
                data_value = int(data, 2)
            else:
                data_value = data

            if not (0 <= data_value <= 65535):
                raise ValueError(f"Data must be between 0 and 65535, got {data_value}")

            # Start with sync bits (001)
            word = self.DATA_SYNC

            # Add data (16 bits)
            word += format(data_value, '016b')

            # Calculate and add parity bit
            parity = self._calculate_parity(word)
            word += str(parity)

            # Verify final length
            if len(word) != 20:
                raise ValueError(f"Invalid word length: {len(word)} bits")

            logger.debug(f"Built data word: {word}")
            return word

        except Exception as error:
            logger.error("Remote Terminal Error while encoding a data word:")
            logger.error(str(error))
            raise

    def _calculate_parity(self, word_without_parity):
        """
        Calculate odd parity bit for the word according to MIL-STD-1553B.
        Returns '1' or '0' to make total number of 1s odd.
        """
        ones_count = word_without_parity.count('1')
        return '1' if ones_count % 2 == 0 else '0'

    def format_message(self, words):
        """
        Format a complete message from a list of words.
        Ensures proper message structure and validates word count.
        """
        try:
            if not words:
                raise ValueError("Empty message")

            # Validate each word length
            for word in words:
                if len(word) != 20:
                    raise ValueError(f"Invalid word length: {len(word)} bits")

            # Join words with proper formatting
            return words

        except Exception as e:
            logger.error(f"Error formatting message: {str(e)}")
            raise
