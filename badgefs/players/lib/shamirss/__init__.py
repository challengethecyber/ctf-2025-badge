
class ShamirSS(object):
    @staticmethod
    def reconstruct_secret(shares):
        """
        Reconstructs a 16-byte secret from exactly 3 Shamir shares.
        
        Args:
            shares: List of 3 (x, y) pairs where x is the share ID and y is the share bytes
            
        Returns:
            The reconstructed secret as bytes
        """
        # GF(256) field operations
        def gf256_add(a, b):
            return a ^ b
        
        def gf256_mul(a, b):
            if a == 0 or b == 0:
                return 0
            p = 0
            for i in range(8):
                if b & 1:
                    p ^= a
                carry = a & 0x80
                a = (a << 1) & 0xFF
                if carry:
                    a ^= 0x1b
                b >>= 1
            return p & 0xFF
        
        def gf256_div(a, b):
            if b == 0:
                raise ValueError("Division by zero")
            if a == 0:
                return 0
            # Calculate b^254 for inverse using square-and-multiply
            exp = 254
            result = 1
            base = b
            while exp > 0:
                if exp & 1:
                    result = gf256_mul(result, base)
                base = gf256_mul(base, base)
                exp >>= 1
            return gf256_mul(a, result)
        
        # Lagrange interpolation optimized for exactly 4 shares
        def lagrange_at_zero(x_values, y_values):
            result = 0
            for i in range(3):
                xi, yi = x_values[i], y_values[i]
                
                # Calculate the Lagrange basis polynomial at 0
                # For each i, compute: ∏(j≠i) (0-xj) / ∏(j≠i) (xi-xj)
                num = 1
                den = 1
                
                for j in range(3):
                    if i == j:
                        continue
                    xj = x_values[j]
                    num = gf256_mul(num, xj)  # When x=0, (0-xj) = xj
                    den = gf256_mul(den, gf256_add(xi, xj))
                
                # Multiply by yi and add to result
                term = gf256_mul(yi, gf256_div(num, den))
                result = gf256_add(result, term)
                
            return result
        
        # Ensure exactly 3 shares
        if len(shares) != 3:
            raise ValueError("Need exactly 3 shares")
        
        # Extract x and y values
        x_values = [share[0] for share in shares]
        
        # Reconstruct each byte
        secret = bytearray(16)
        for i in range(16):
            y_values = [share[1][i] for share in shares]
            secret[i] = lagrange_at_zero(x_values, y_values)
        
        return bytes(secret)
