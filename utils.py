import hashlib

def string_to_hash(input_string: str, hash_type: str = "sha256") -> str:
    """
    Converts a string into a hash using the specified hashing algorithm.

    :param input_string: String to convert into a hash.
    :param hash_type: Hashing algorithm ('md5', 'sha1', 'sha256', 'sha512', etc.).
    :return: Hash string.
    """
    # Convert the string to bytes
    encoded_string = input_string.encode('utf-8')

    # Create the hash using the specified algorithm
    hash_function = getattr(hashlib, hash_type)
    hash_object = hash_function(encoded_string)

    # Return the hash in hexadecimal format
    return hash_object.hexdigest()
