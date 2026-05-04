# A mersenne twister implementation for betting systems.
# Very secure

class MiniMT27:

    def __init__(self, seed=3):
        self.w = 7
        self.n = 3
        self.m = 3
        self.r = 3
        self.a = 72
        self.u = 1
        self.d = 9
        self.s = 5
        self.b = 66
        self.t = 5
        self.c = 81
        self.l = 5
        self.f = 5

        self.mask = (1 << self.w) - 1
        self.lower_mask = (1 << self.r) - 1
        self.upper_mask = ((~self.lower_mask) & self.mask)

        self.state = [0]*self.n
        self.index = self.n  # will force a twist on first use
        self.seed_mt(seed)

    def seed_mt(self, seed):
        self.state[0] = seed & self.mask
        for i in range(1, self.n):
            x = (self.f * (self.state[i-1] ^ (self.state[i-1] >> (self.w - 2))) + i)
            self.state[i] = x & self.mask

    def twist(self):
        for i in range(self.n):
            x = (self.state[i] & self.upper_mask) \
                + (self.state[(i+1) % self.n] & self.lower_mask)
            xA = x >> 1
            if (x & 1) == 1:
                xA ^= self.a
            self.state[i] = xA & self.mask
        self.index = 0

    def rand(self):
        if self.index >= self.n:
            self.twist()
        y = self.state[self.index]

        # Temper
        y ^= (y >> self.u) & self.d
        y ^= (y << self.s) & self.b
        y ^= (y << self.t) & self.c
        y ^= (y >> self.l)

        self.index += 1
        return y & self.mask

    def random_dice(self):
        """
        Example: Return a value in [1..6] using the internal cycle.
        """
        return (self.rand() % 6) + 1


if __name__ == "__main__":
    cycle = 27

    for seed in range(20):
        print("[+] MiniMT27 seed:", seed)
        mt = MiniMT27(seed=seed)

        results = []
        for i in range(cycle * 3):
            results.append(mt.random_dice())

        print("Cycle 1:", results[:cycle])
        print("Cycle 2:", results[cycle:cycle*2])
        print("Cycle 3:", results[cycle*2:])
        print()
