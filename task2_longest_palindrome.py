def longest_palindrome(s: str) -> str:
    """Возвращает самую длинную подстроку-палиндром.

    Метод «расширение от центра»: у палиндрома есть центр — символ
    (нечётная длина) или промежуток между двумя символами (чётная длина).
    Для каждого центра расширяемся влево и вправо, пока символы совпадают.
    Сложность: O(n^2) по времени, O(1) по памяти.

    Если палиндромов максимальной длины несколько, возвращается
    самый левый из них. Для пустой строки и строки из одного символа
    возвращается сама строка.
    """
    if len(s) < 2:
        return s

    start, best_len = 0, 1
    
    def expand(left: int, right: int) -> int:

        while left >= 0 and right < len(s) and s[left] == s[right]:
            left -= 1
            right += 1

        return right - left - 1

    for i in range(len(s)):
        odd = expand(i, i)
        even = expand(i, i + 1)
        length = max(odd, even)
        if length > best_len:
            best_len = length
            start = i - (length - 1) // 2

    return s[start:start + best_len]