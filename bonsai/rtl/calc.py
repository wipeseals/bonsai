from functools import reduce


class Calc:
    @staticmethod
    def byte_width(width: int) -> int:
        """
        Convert bit width to byte width
        e.g.
            1bit -> 1byte
            8bit -> 1byte
            16bit -> 2byte
            32bit -> 4byte
            64bit -> 8byte
            65bit -> 9byte
        """
        return (width + 7) // 8

    @staticmethod
    def is_power_of_2(n: int) -> bool:
        """
        Check if n is a power of 2

        0x400 & 0x3FF == 0 (2^10) のような1つ低い値とのビットANDが1bitだけになることを利用
        """
        return n != 0 and (n & (n - 1)) == 0

    @staticmethod
    def even_parity(data: int, data_width: int) -> int:
        """
        Python上の計算でパリティビットを求める (奇数パリティ)
        """
        return reduce(lambda x, y: x ^ y, [data >> i & 1 for i in range(data_width)])

    @staticmethod
    def odd_parity(data: int, data_width: int) -> int:
        """
        Python上の計算でパリティビットを求める (偶数パリティ)
        """
        return 1 - Calc.even_parity(data, data_width)
