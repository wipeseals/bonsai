class Calc:
    def sign_extend(data: int, num_bit_width: int):
        """
        Sign extend the data to the given bit width
        """
        if data & (1 << (num_bit_width - 1)):
            data -= 1 << num_bit_width
        return data
