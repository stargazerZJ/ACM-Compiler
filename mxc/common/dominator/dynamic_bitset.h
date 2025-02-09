//
// Created by zj on 8/22/2024.
//

#pragma once
#include <vector>
#include <bit>
#include <cstring>
#include <cstdint>
#include <iostream>
#include <algorithm>
#include <ranges>
#include <cassert>

class dynamic_bitset {
    using ull = unsigned long long;

public:
    dynamic_bitset() = default;

    ~dynamic_bitset() = default;

    dynamic_bitset(const dynamic_bitset&) = default;

    dynamic_bitset& operator=(const dynamic_bitset&) = default;

    // Initializes the bitset with size n, all bits set to 0.
    explicit dynamic_bitset(std::size_t n) : s(n), v(VSize()) {}

    /**
     * @brief Initializes the bitset from a string.
     * Assumes the string is valid and that the lowest bit is at the start.
     * For example, if a = "0010", then:
     * a's 0th bit is 0,
     * a's 1st bit is 0,
     * a's 2nd bit is 1,
     * a's 3rd bit is 0.
     */
    explicit dynamic_bitset(const std::string& str) : dynamic_bitset(str.size()) {
        ull x = 0;
        for (size_t i = 0; i < str.size(); i++) {
            x |= static_cast<ull>(str[i] == '1') << (i & (L - 1));
            if ((i & (L - 1)) == L - 1) {
                v[i >> LB] = x;
                x          = 0;
            }
        }
        if (!str.empty() && x > 0) {
            v.back() = x;
        }
    }

    // Accesses the nth bit value. The indexing is 0-based like in a vector.
    bool operator[](std::size_t n) const {
        const auto& x = v[n >> LB];
        return x & (1ull << (n & (L - 1)));
    }

    // Sets the nth bit to a specified value.
    dynamic_bitset& set(std::size_t n, bool val = true) {
        auto& x = v[n >> LB];
        if (val) {
            x |= (1ull << (n & (L - 1)));
        } else {
            x &= ~(1ull << (n & (L - 1)));
        }
        return *this;
    }

    // Inserts a new bit at the end, increase the bitset size by one.
    dynamic_bitset& push_back(bool val = false) {
        ++s;
        if ((s & (L - 1)) == 1) v.emplace_back();
        set(s - 1, val);
        return *this;
    }

    // Returns true if all bits are 0, false otherwise.
    [[nodiscard]] bool none() const {
        for (auto x : v) {
            if (x) {
                return false;
            }
        }
        return true;
    }

    // Returns true if all bits are 1, false otherwise.
    [[nodiscard]] bool all() const {
        if (v.empty()) {
            return true;
        }
        for (auto x : v) {
            if (~x) {
                return false;
            }
        }
        return v.back() == tailMask(s);
    }

    // Returns the number of 1s in the bitset.
    [[nodiscard]] size_t count() const {
        size_t res = 0;
        for (auto x : v) {
            res += std::popcount(x);
        }
        return res;
    }

    // Returns the length of the bitset.
    [[nodiscard]] std::size_t size() const {
        return s;
    }

    // Compare two bitsets.
    [[nodiscard]] bool operator==(const dynamic_bitset& rhs) const {
        return s == rhs.s && v == rhs.v;
    }

    /**
     * All bitwise operations follow these rules:
     * The smaller length of the two bitsets will be used in the operation.
     * In other words, operations are performed only on their overlapping parts, with other parts unchanged.
     * The length of the bitset should not change before and after the operation.
     *
     * For example:
     * a = "10101", b = "1100"
     * After a |= b, a should become "11101"
     * After b |= a, b should become "1110"
     * After a &= b, a should become "10001"
     * After b &= a, b should become "1000"
     * After a ^= b, a should become "01101"
     * After b ^= a, b should become "0110"
     */

    // OR operation, returns a reference to the modified bitset. a |= b means a = a | b
    dynamic_bitset& operator|=(const dynamic_bitset& rhs) {
        size_t l  = std::min(s, rhs.s);
        size_t vl = std::min(v.size(), rhs.v.size());
        if (vl > 0) {
            for (size_t i = 0; i < vl - 1; i++) {
                v[i] |= rhs.v[i];
            }
            v[vl - 1] |= rhs.v[vl - 1] & tailMask(l);
        }
        return *this;
    }

    // AND operation, returns a reference to the modified bitset. a &= b means a = a & b
    dynamic_bitset& operator&=(const dynamic_bitset& rhs) {
        size_t l  = std::min(s, rhs.s);
        size_t vl = std::min(v.size(), rhs.v.size());
        if (vl > 0) {
            for (size_t i = 0; i < vl - 1; i++) {
                v[i] &= rhs.v[i];
            }
            v[vl - 1] &= rhs.v[vl - 1] | ~tailMask(l);
        }
        return *this;
    }

    // XOR operation, returns a reference to the modified bitset. a ^= b means a = a ^ b
    dynamic_bitset& operator^=(const dynamic_bitset& rhs) {
        size_t l  = std::min(s, rhs.s);
        size_t vl = std::min(v.size(), rhs.v.size());
        if (vl > 0) {
            for (size_t i = 0; i < vl - 1; i++) {
                v[i] ^= rhs.v[i];
            }
            v[vl - 1] ^= rhs.v[vl - 1] & tailMask(l);
        }
        return *this;
    }

    /**
     * @brief Left shifts the bitset by n positions. Similar to unsigned integer left shifts, the lower bits will be set to 0.
     * For example, if a = "1110"
     * After a <<= 3, a should become "0001110"
     * @return Returns a reference to the modified bitset.
     */
    dynamic_bitset& operator<<=(std::size_t n) {
        s += n;
        v.resize(VSize());
        if (v.empty()) {
            return *this;
        }
        ull lst = v[v.size() - 1 - (n >> LB)];
        for (size_t i = v.size() - 1; i > (n >> LB); --i) {
            v[i] = n & (L - 1) ? v[i - (n >> LB) - 1] >> (L - (n & (L - 1))) | lst << (n & (L - 1)) : lst;
            lst  = v[i - (n >> LB) - 1];
        }
        for (size_t i = 0; i < (n >> LB); ++i) {
            v[i] = 0;
        }
        v[(n >> LB)] = lst << (n & (L - 1));
        return *this;
    }

    /**
     * @brief Right shifts the bitset by n positions. Similar to unsigned integer right shifts, lower bits are discarded.
     * For example, if a = "10100"
     * After a >>= 2, a should become "100"
     * After a >>= 9, a should become "" (i.e., length is 0)
     * @return Returns a reference to the modified bitset.
     */
    dynamic_bitset& operator>>=(std::size_t n) {
        if (s <= n) {
            return *this = dynamic_bitset();
        }
        s -= n;
        ull lst = v[n >> LB] >> (n & (L - 1));
        for (size_t i = 0; i < v.size() - (n >> LB) - 1; ++i) {
            v[i] = n & (L - 1) ? lst | v[i + (n >> LB) + 1] << (L - (n & (L - 1))) : lst;
            lst  = v[i + (n >> LB) + 1] >> (n & (L - 1));
        }
        v[v.size() - (n >> LB) - 1] = lst;
        v.resize(VSize());
        return *this;
    }

    // Sets all bits to 1.
    dynamic_bitset& set() {
        if (v.empty()) {
            return *this;
        }
        for (size_t i = 0; i < v.size() - 1; i++) {
            v[i] = ~0;
        }
        v.back() = tailMask(s);
        return *this;
    }

    // Flips (inverts) all bits.
    dynamic_bitset& flip() {
        if (v.empty()) {
            return *this;
        }
        for (size_t i = 0; i < v.size() - 1; i++) {
            v[i] = ~v[i];
        }
        v.back() = (~v.back()) & tailMask(s);
        return *this;
    }

    // Resets all bits to 0.
    dynamic_bitset& reset() {
        if (v.empty()) {
            return *this;
        }
        for (size_t i = 0; i < v.size() - 1; i++) {
            v[i] = 0;
        }
        v.back() = 0;
        return *this;
    }

    // Returns the indices of ones
    std::vector<int> get_ones() {
        std::vector<int> indices;
        for (size_t i = 0; i < v.size(); ++i) {
            ull x = v[i];
            while (x != 0) {
                int bit_pos = std::countr_zero(x);
                indices.push_back(i * L + bit_pos);
                x &= (x - 1);
            }
        }
        return indices;
    }

private:
    static constexpr size_t L = 64, LB = 6;
    size_t                  s = 0;
    std::vector<ull>        v;

    [[nodiscard]] size_t VSize() const {
        return (s + L - 1) >> LB;
    }

    static constexpr ull tailMask(size_t k) {
        if (k & (L - 1)) {
            return (1ull << (k & (L - 1))) - 1;
        } else {
            return ~0ull;
        }
    }
};
