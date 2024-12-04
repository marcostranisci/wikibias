import hashlib
def string_to_hash(input_string: str, hash_type: str = "sha256") -> str:
    """
    Trasforma una stringa in un hash usando il tipo di hashing specificato.

    :param input_string: Stringa da convertire in hash.
    :param hash_type: Tipo di hash ('md5', 'sha1', 'sha256', 'sha512', ecc.).
    :return: Stringa hash.
    """
    # Converti la stringa in bytes
    encoded_string = input_string.encode('utf-8')

    # Crea l'hash in base al tipo specificato
    hash_function = getattr(hashlib, hash_type)
    hash_object = hash_function(encoded_string)

    # Restituisci l'hash in formato esadecimale
    return hash_object.hexdigest()
