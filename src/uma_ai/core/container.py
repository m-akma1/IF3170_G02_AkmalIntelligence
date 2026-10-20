from __future__ import annotations


class Container:
    """
    Representasi grid 3D truk. `width`, `length`, `height` adalah dimensi truk. Terdapat tiga array 1D:
    - `cols` merepresentasikan penampang bidang xy dengan z sebagai bitmask. Bit z = 1 untuk cols[x * length + y] jika sel (x, y, z) terisi.
    - `fragile` sama dengan `cols` untuk paket fragile saja. Bit z = 1 untuk fragile[x * length + y] jika sel (x, y, z) terisi oleh paket fragile.
    - `owner` menunjukkan paket yang menempati sel (x, y, z) di `owner[(x * length + y) * height + z] = package` atau None jika kosong.
    - `top` menunjukkan z puncak paket yang menempati sel (x, y, z) di `top[(x * length + y) * height + z] = z_top`.
    - `yend` (y end) menunjukkan y belakang paket yang menempati sel (x, y., z) di `yend[(x * length + y) * height + z] = y_end`.
    - `rows` merepresentasikan penampang bidang xz dengan y sebagai bitmask. Bit y = 1 untuk rows[x * height + z] jika sel (x, y, z) terisi.

        Overlap dan out of bounds dianggap hard constraint.
    """
    __slots__ = ("width", "length", "height", "cols", "fragile", "rows", "owner", "top", "yend")

    def __init__(self, width: int, length: int, height: int):
        self.width, self.length, self.height = width, length, height
        self.cols = [0] * (width * length)
        self.fragile = [0] * (width * length)
        self.rows = [0] * (width * height)
        self.owner: list[object | None] = [None] * (width * length * height)
        self.top = [0] * (width * length * height)
        self.yend = [0] * (width * length * height)

    def copy(self) -> Container:
        other = Container.__new__(Container)
        other.width, other.length, other.height = self.width, self.length, self.height
        other.cols, other.fragile, other.rows = self.cols[:], self.fragile[:], self.rows[:]
        other.owner, other.top, other.yend = self.owner[:], self.top[:], self.yend[:]
        return other

    def in_bound(self, x: int, y: int, z: int, dx: int, dy: int, dz: int) -> bool:
        return (
            x >= 0 and y >= 0 and z >= 0
            and x + dx <= self.width and y + dy <= self.length and z + dz <= self.height
        )

    def mark(self, package: object, x: int, y: int, z: int, dx: int, dy: int, dz: int, fragile: bool, on: bool):
        """Menandai (on=True) atau menghapus (on=False) sel paket. Tidak memeriksa overlap."""
        m = ((1 << dz) - 1) << z
        cols, fragile_bits, rows, owner, top, yend = self.cols, self.fragile, self.rows, self.owner, self.top, self.yend
        L, H = self.length, self.height
        who = package if on else None
        z1, y1 = z + dz, y + dy
        for xx in range(x, x + dx):
            r = xx * L
            for yy in range(y, y + dy):
                c = r + yy
                if on:
                    cols[c] |= m
                    if fragile:
                        fragile_bits[c] |= m
                else:
                    cols[c] &= ~m
                    if fragile:
                        fragile_bits[c] &= ~m
                b = c * H
                for zz in range(z, z1):
                    owner[b + zz] = who
                    top[b + zz] = z1
                    yend[b + zz] = y1
            ym = ((1 << dy) - 1) << y
            for zz in range(xx * H + z, xx * H + z1):
                if on:
                    rows[zz] |= ym
                else:
                    rows[zz] &= ~ym

    def mask(self, x: int, y: int, dx: int, dy: int) -> int:
        """OR seluruh kolom di alas (x, y, dx, dy)."""
        cols, L = self.cols, self.length
        m = 0
        for xx in range(x, x + dx):
            r = xx * L
            for yy in range(y, y + dy):
                m |= cols[r + yy]
        return m

    def fits(self, x: int, y: int, z: int, dx: int, dy: int, dz: int) -> bool:
        """True jika kotak di dalam batas truk dan semua selnya kosong."""
        if not self.in_bound(x, y, z, dx, dy, dz):
            return False
        m = ((1 << dz) - 1) << z
        cols, L = self.cols, self.length
        for xx in range(x, x + dx):
            r = xx * L
            for yy in range(y, y + dy):
                if cols[r + yy] & m:
                    return False
        return True

    def drop_z(self, x: int, y: int, dx: int, dy: int, dz: int) -> int | None:
        """
        z terendah yang valid sesuai constraint untuk tempat kotak muat pada alas (x, y), atau None jika tidak ada.
        """
        if x < 0 or y < 0 or x + dx > self.width or y + dy > self.length or dz > self.height:
            return None
        m = self.mask(x, y, dx, dy)
        window = (1 << dz) - 1
        for z in range(self.height - dz + 1):
            if not (m >> z) & window:
                return z
        return None

    def fall_z(self, x: int, y: int, z: int, dx: int, dy: int) -> int:
        """z hasil jatuh bebas dari z ke bawah. Kotak harus sudah dihapus dari grid."""
        m = self.mask(x, y, dx, dy)
        while z > 0 and not (m >> (z - 1)) & 1:
            z -= 1
        return z

    def owners_in(self, x0: int, x1: int, y0: int, y1: int, z0: int, z1: int) -> set:
        """Himpunan paket yang mengisi sel di dalam kotak [x0, x1) x [y0, y1) x [z0, z1) sesuai batas truk."""
        x0, y0, z0 = max(x0, 0), max(y0, 0), max(z0, 0)
        x1, y1, z1 = min(x1, self.width), min(y1, self.length), min(z1, self.height)
        found = set()
        if x0 >= x1 or y0 >= y1 or z0 >= z1:
            return found
        m = ((1 << (z1 - z0)) - 1) << z0
        cols, owner, top = self.cols, self.owner, self.top
        L, H = self.length, self.height
        for xx in range(x0, x1):
            r = xx * L
            for yy in range(y0, y1):
                c = r + yy
                bits = cols[c] & m
                b = c * H
                while bits:
                    zz = (bits & -bits).bit_length() - 1  # sel terisi terendah
                    found.add(owner[b + zz])
                    bits &= -1 << top[b + zz]             # lompati sisa paket itu
        return found

    def lane_owners(self, x0: int, x1: int, y0: int, y1: int, z0: int, z1: int) -> set:
        """Sama dengan owners_in, tetapi memindai baris sepanjang y"""
        x0, y0, z0 = max(x0, 0), max(y0, 0), max(z0, 0)
        x1, y1, z1 = min(x1, self.width), min(y1, self.length), min(z1, self.height)
        found = set()
        if x0 >= x1 or y0 >= y1 or z0 >= z1:
            return found
        m = ((1 << (y1 - y0)) - 1) << y0
        rows, owner, yend = self.rows, self.owner, self.yend
        L, H = self.length, self.height
        for xx in range(x0, x1):
            for zz in range(z0, z1):
                bits = rows[xx * H + zz] & m
                while bits:
                    yy = (bits & -bits).bit_length() - 1  # sel terisi terdekat ke pintu
                    k = (xx * L + yy) * H + zz
                    found.add(owner[k])
                    bits &= -1 << yend[k]                 # lompati sisa paket itu
        return found

    def support_area(self, x: int, y: int, z: int, dx: int, dy: int) -> int:
        """Jumlah kolom alas yang dapat menopang"""
        if z == 0:
            return dx * dy
        bit = 1 << (z - 1)
        cols, L = self.cols, self.length
        area = 0
        for xx in range(x, x + dx):
            r = xx * L
            for yy in range(y, y + dy):
                if cols[r + yy] & bit:
                    area += 1
        return area

    def fragile_owners(self, x: int, y: int, dx: int, dy: int, zl: int) -> set:
        """Paket fragile yang menempati lapisan zl pada alas (x, y, dx, dy)."""
        found = set()
        if zl < 0 or zl >= self.height:
            return found
        bit = 1 << zl
        fragile, owner = self.fragile, self.owner
        L, H = self.length, self.height
        for xx in range(x, x + dx):
            r = xx * L
            for yy in range(y, y + dy):
                c = r + yy
                if fragile[c] & bit:
                    found.add(owner[c * H + zl])
        return found

    def is_full(self, x: int, y: int) -> bool:
        """True jika kolom (x, y) penuh atau di luar truk."""
        if not (0 <= x < self.width and 0 <= y < self.length):
            return True
        return self.cols[x * self.length + y] == (1 << self.height) - 1
