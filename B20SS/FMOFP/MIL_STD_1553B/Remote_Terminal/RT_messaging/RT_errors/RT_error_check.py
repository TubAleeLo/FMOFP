####
#   Filename:   RT_error_check.py
#
#   Class:      RT_error_checkers   
#   Functions:          check_command_word(self, rt_address, t_or_r, sub_add_or_mode_code, wd_count)    
#                       check_data_word(self, data_word)
#                       check_sync_bits(self, word, word_type)
#                       check_parity(self, word)
#                       validate_rt_address(self, address)
#
####

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class RT_error_checkers:
        # MIL-STD-1553B sync patterns
        COMMAND_SYNC = "100"  # Command/Status word sync pattern
        DATA_SYNC = "001"     # Data word sync pattern
        
        def check_command_word(self, rt_address, t_or_r, sub_add_or_mode_code, wd_count):
                """
                Validate components of a command word according to MIL-STD-1553B.
                
                Args:
                    rt_address: RT address bits (5 bits)
                    t_or_r: Transmit/Receive bit (1 bit)
                    sub_add_or_mode_code: Subaddress or Mode Code (5 bits)
                    wd_count: Word Count/Mode Code (5 bits)
                    
                Returns:
                    bool: True if valid, False otherwise
                """
                try:
                        if  len(rt_address) == 5:
                                pass
                        else:
                                raise Exception("Command Word: Invalid RT Address")
                
                        if len(t_or_r) == 1:
                                pass
                        else:
                                raise Exception("Command Word: Invalid T/R")
                        
                        if len(sub_add_or_mode_code) == 5:
                                pass
                        else:
                                raise Exception("Command Word: Invalid Subaddress/Mode Code")
                        
                        if len(wd_count) == 5:
                                pass
                                return True
                        else:
                                raise Exception("Command Word: Invalid Word Count")
                        
                except Exception as error:
                                logger.error("Remote Terminal Error:")
                                logger.error("{}".format(str(error)))
                                return False

        def check_data_word(self, data_word):
                """
                Validate a data word is the correct length (16 bits).
                
                Args:
                    data_word: Data word bits (16 bits)
                    
                Returns:
                    bool: True if valid, False otherwise
                """
                try:
                        if len(data_word) == 16:  # Correct data word length per MIL-STD-1553B
                                return True
                        else:
                                raise Exception(f"Invalid Data Word length: {len(data_word)} (expected 16)")
                
                except Exception as error:
                                logger.error("Remote Terminal Error:")
                                logger.error("{}".format(str(error)))
                                return False
                        
        def check_character(self, char):
                try:
                        if not str.isdigit(char):
                                raise Exception("Address contains nondigit character")
                        
                        elif not (0 <= int(char, 2) <= 31):
                                raise Exception("Address outside valid range. 0-255")
                        else:
                                return True                  
                        
                except Exception as error:
                                logger.error("Remote Terminal Error:")
                                logger.error("{}".format(str(error)))
                                return False

        def check_sync_bits(self, word, word_type='command'):
                """
                Check sync bits for different word types according to MIL-STD-1553B.
                Command/Status words use '100', Data words use '001'.
                """
                try:
                        if len(word) < 3:
                                logger.warning(f"Word too short for sync check: {len(word)}")
                                return False
                                
                        sync_bits = word[:3]
                        
                        if word_type.lower() in ['command', 'status']:
                                return sync_bits == self.COMMAND_SYNC
                        elif word_type.lower() == 'data':
                                return sync_bits == self.DATA_SYNC
                        else:
                                logger.warning(f"Invalid word type for sync check: {word_type}")
                                return False
                        
                except Exception as e:
                        logger.error(f"Sync bits check failed: {str(e)}")
                        return False

        def check_parity(self, word):
                """
                Calculate odd parity bit for a binary word according to MIL-STD-1553B.
                Validates that the total number of 1s is odd.
                """
                try:
                        if len(word) != 20:
                                logger.warning(f"Invalid word length for parity check: {len(word)}")
                                return False
                                
                        # Count number of 1s in the word (excluding parity bit)
                        ones_count = word[:19].count('1')
                        parity_bit = int(word[19])
                        
                        # For odd parity, total should be odd
                        return (ones_count + parity_bit) % 2 == 1
                        
                except Exception as e:
                        logger.error(f"Parity check failed: {str(e)}")
                        return False

        def validate_rt_address(self, address):
                """
                Validate RT address according to MIL-STD-1553B (0-31).
                """
                try:
                        if isinstance(address, str):
                                if not all(c in '01' for c in address):
                                        raise Exception("RT address contains non-binary characters")
                                addr_int = int(address, 2)
                        else:
                                addr_int = address
                                
                        # Valid range for 5-bit RT address is 0-31
                        if not (0 <= addr_int <= 31):
                                raise Exception(f"RT address outside valid range (0-31): {addr_int}")
                        return True
                        
                except Exception as e:
                        logger.error(f"RT address validation failed: {str(e)}")
                        return False

        def check_word_format(self, word, word_type='command'):
                """
                Comprehensive check of word format including length, sync bits, and parity.
                """
                try:
                        # Check length
                        if len(word) != 20:
                                logger.warning(f"Invalid word length: {len(word)}")
                                return False
                                
                        # Check sync bits
                        if not self.check_sync_bits(word, word_type):
                                logger.warning(f"Invalid sync bits for {word_type} word")
                                return False
                                
                        # Check characters
                        if not all(c in '01' for c in word):
                                logger.warning("Invalid characters in word")
                                return False
                                
                        # Check parity
                        if not self.check_parity(word):
                                logger.warning("Invalid parity")
                                return False
                                
                        return True
                
                except Exception as e:
                        logger.error(f"Word format check failed: {str(e)}")
                        return False
