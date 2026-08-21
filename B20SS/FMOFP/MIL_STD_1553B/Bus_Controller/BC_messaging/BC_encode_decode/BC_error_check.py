####
#   Filename:   BC_error_check.py
#
#   Class:      BC_error_checkers   
#   Functions:          check_command_word(self, rt_address, t_or_r, sub_add_or_mode_code, wd_count)    
#                       check_data_word(self, data_word)
#                       check_sync_bits(self, word, word_type)
#                       check_parity(self, word)
#                       check_word_format(self, word, word_type)
#                       check_frame_format(self, frame)
#
####
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class BC_error_checkers:
        # MIL-STD-1553B sync patterns
        COMMAND_SYNC = "100"  # Command/Status word sync pattern
        DATA_SYNC = "001"     # Data word sync pattern
        
        def check_character(self, char):
                """Check if character string contains only valid binary digits."""
                try:
                        return all(c in '01' for c in char)
                except Exception as e:
                        logger.error(f"Character check failed: {str(e)}")
                return False

        def check_parity(self, word):
                """
                Check odd parity for a complete 20-bit word.
                Returns True if parity is valid (odd number of 1s).
                """
                try:
                        if len(word) != 20:
                                logger.error(f"Invalid word length for parity check: {len(word)}")
                                return False
                
                        # Count total number of 1s (including parity bit)
                        ones_count = word.count('1')
                        return ones_count % 2 == 1  # Should be odd for valid parity
                
                except Exception as e:
                        logger.error(f"Parity check failed: {str(e)}")
                        return False

        def check_sync_bits(self, word, word_type='command'):
                """
                Check sync bits for different word types according to MIL-STD-1553B.
                Command/Status words use '100', Data words use '001'.
                """
                try:
                        if len(word) < 3:
                                logger.error(f"Word too short for sync check: {len(word)}")
                                return False
                                
                        sync_bits = word[:3]
                        
                        if word_type.lower() in ['command', 'status']:
                                return sync_bits == self.COMMAND_SYNC
                        elif word_type.lower() == 'data':
                                return sync_bits == self.DATA_SYNC
                        else:
                                logger.error(f"Invalid word type for sync check: {word_type}")
                                return False
                        
                except Exception as e:
                        logger.error(f"Sync bits check failed: {str(e)}")
                        return False

        def check_word_format(self, word, word_type='command'):
                """
                Comprehensive check of word format including length, sync bits, and parity.
                """
                try:
                        # Check length
                        if len(word) != 20:
                                logger.error(f"Invalid word length: {len(word)}")
                                return False
                                
                        # Check sync bits
                        if not self.check_sync_bits(word, word_type):
                                logger.error(f"Invalid sync bits for {word_type} word")
                                return False
                                
                        # Check characters
                        if not self.check_character(word):
                                logger.error("Invalid characters in word")
                                return False
                                
                        # Check parity
                        if not self.check_parity(word):
                                logger.error("Invalid parity")
                                return False
                                
                        return True
                
                except Exception as e:
                        logger.error(f"Word format check failed: {str(e)}")
                        return False

        def check_frame_format(self, frame):
                """
                Validate complete message frame format.
                """
                try:
                        if not frame or not isinstance(frame, list):
                                logger.error("Invalid frame format")
                                return False
                                
                        # Check command word (first word)
                        if not self.check_word_format(frame[0], 'command'):
                                logger.error("Invalid command word format")
                                return False
                                
                        # Check data words if present
                        for word in frame[1:]:
                                if not self.check_word_format(word, 'data'):
                                        logger.error("Invalid data word format")
                                        return False
                        
                        return True
                
                except Exception as e:
                        logger.error(f"Frame format check failed: {str(e)}")
                        return False

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
                        if len(rt_address) == 5:
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
                                return True
                        else:
                                raise Exception("Command Word: Invalid Word Count")
                        
                except Exception as error:
                        logger.error("Bus Controller Error:")
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
                        logger.error("Bus Controller Error:")
                        logger.error("{}".format(str(error)))
                        return False
                        
        def validate_rt_address(self, rt_address):
                """
                Validate RT address is in the valid range (0-31).
                
                Args:
                    rt_address: RT address to validate
                    
                Returns:
                    bool: True if valid, False otherwise
                """
                try:
                        if isinstance(rt_address, str):
                                if not all(c in '01' for c in rt_address):
                                        raise Exception("RT address contains non-binary characters")
                                addr = int(rt_address, 2)
                        else:
                                addr = int(rt_address)
                                
                        if not (0 <= addr <= 31):
                                raise Exception(f"RT address outside valid range (0-31): {addr}")
                        return True
                                
                except Exception as error:
                        logger.error("Bus Controller Error:")
                        logger.error("{}".format(str(error)))
                        return False
                        
        # A second check_character()/check_parity() pair used to be defined
        # here, silently shadowing the correct ones above (Python keeps only
        # the later definition of a duplicate method name). That silently
        # broke both:
        #   - check_character() became a digit/range check for an "Address"
        #     (error messages literally said "Address contains..."), not the
        #     binary-only-character check check_word_format() actually needs
        #     when validating a 20-bit word -- and its own range condition,
        #     `int(char) >= 0 or int(char) <= 255`, is always true for any
        #     non-negative int, so it silently accepted anything anyway.
        #     validate_rt_address() above already covers real address
        #     validation correctly, making this redundant on top of wrong.
        #   - check_parity() implemented EVEN parity (comparing the parity
        #     bit against num_ones % 2 directly), contradicting MIL-STD-1553B
        #     (which requires ODD parity) and contradicting the two other
        #     parity checks elsewhere in this codebase
        #     (BC_words_decoder._validate_parity, RT_error_checkers.check_parity),
        #     both of which correctly implement odd parity like the
        #     definitions above.
        # BC_error_checkers isn't instantiated anywhere in the codebase today,
        # so this had no live impact, but removing the dead duplicates fixes
        # the landmine for whenever this class is wired up (production
        # readiness reanalysis, duplicate-method systemic scan).
