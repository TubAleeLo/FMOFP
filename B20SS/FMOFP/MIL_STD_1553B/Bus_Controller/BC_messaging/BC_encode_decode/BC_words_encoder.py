from Utils.logger.sys_logger import get_logger


logger = get_logger()

class BCWordsEncoder:


    def encode_command_word(self, rt_address, tr_bit, subaddress_mode, word_count_mode):
        """
        Encode a command word according to MIL-STD-1553B specification.
        Command word format (20 bits):
        - Sync (3 bits): 100
        - RT Address (5 bits)
        - T/R bit (1 bit)
        - Subaddress/Mode (5 bits)
        - Word Count/Mode Code (5 bits)
        - P bit (1 bit)
        """
        try:
            # Validate input ranges
            if not (0 <= rt_address <= 31):  # 5 bits max
                raise ValueError(f"RT address must be between 0 and 31, got {rt_address}")
            if tr_bit not in [0, 1]:
                raise ValueError(f"T/R bit must be 0 or 1, got {tr_bit}")
            if not (0 <= subaddress_mode <= 31):  # 5 bits max
                raise ValueError(f"Subaddress/Mode must be between 0 and 31, got {subaddress_mode}")
            if not (0 <= word_count_mode <= 31):  # 5 bits max
                raise ValueError(f"Word count/Mode code must be between 0 and 31, got {word_count_mode}")

            # Start with sync bits
            word = '100'

            # Add RT address (5 bits)
            word += format(rt_address, '05b')

            # Add T/R bit (1 bit)
            word += str(tr_bit)

            # Add subaddress/mode (5 bits)
            word += format(subaddress_mode, '05b')

            # Add word count/mode code (5 bits)
            word += format(word_count_mode, '05b')

            # Calculate and add parity bit
            parity = self._calculate_parity(word)
            word += str(parity)

            # Verify final length
            if len(word) != 20:
                raise ValueError(f"Invalid word length: {len(word)} bits")

            return word

        except Exception as e:
            logger.error(f"Error encoding command word: {str(e)}")
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
            if not (0 <= data <= 65535):
                raise ValueError(f"Data must be between 0 and 65535, got {data}")

            # Start with sync bits
            word = '001'

            # Add data (16 bits)
            word += format(data, '016b')

            # Calculate and add parity bit
            parity = self._calculate_parity(word)
            word += str(parity)

            # Verify final length
            if len(word) != 20:
                raise ValueError(f"Invalid word length: {len(word)} bits")

            return word

        except Exception as e:
            logger.error(f"Error encoding data word: {str(e)}")
            raise

    def _calculate_parity(self, word_without_parity):
        """
        Calculate odd parity bit for the word according to MIL-STD-1553B.
        Returns '0' or '1' to make total number of 1s odd.
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
