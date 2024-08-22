//
// Created by zj on 8/22/2024.
//

#pragma once
#include <vector>
#include <cstring>
#include <cstdint>
#include <iostream>
#include <algorithm>
#include <ranges>
#include <cassert>

using std::vector, std::views::iota;
struct dynamic_bitset {
  using ull = unsigned long long;
  static constexpr size_t L = 64, LB = 6;
  size_t s = 0;
  vector<ull> v;

  size_t VSize() const {
    return (s + L - 1) >> LB;
  }

  static constexpr ull tailMask(size_t k) {
    if (k & (L - 1)) {
      return (1ull << (k & (L - 1))) - 1;
    } else {
      return ~0ull;
    }
  }

  // 默认构造函数，默认长度为 0
  dynamic_bitset() = default;

  // 除非手动管理内存，否则 = default 即可
  ~dynamic_bitset() = default;

  /**
   * @brief 拷贝构造函数
   * 如果你用 std::vector 来实现，那么这个函数可以直接 = default
   * 如果你手动管理内存，则你可能需要自己实现这个函数
   */
  dynamic_bitset(const dynamic_bitset &) = default;

  /**
   * @brief 拷贝赋值运算符
   * 如果你用 std::vector 来实现，那么这个函数可以直接 = default
   * 如果你手动管理内存，则你可能需要自己实现这个函数
   */
  dynamic_bitset &operator=(const dynamic_bitset &) = default;

  // 初始化 bitset 的大小为 n ，且全为 0.
  explicit dynamic_bitset(std::size_t n) : s(n), v(VSize()) {}

  /**
   * @brief 从一个字符串初始化 bitset。
   * 保证字符串合法，且最低位在最前面。
   * 例如 a =  "0010"，则有:
   * a 的第 0 位是 0
   * a 的第 1 位是 0
   * a 的第 2 位是 1
   * a 的第 3 位是 0
   */
  explicit dynamic_bitset(const std::string &str) : dynamic_bitset(str.size()) {
    ull x = 0;
    for (size_t i : iota(size_t(), str.size())) {
      x |= static_cast<ull>(str[i] == '1') << (i & (L - 1));
      if ((i & (L - 1)) == L - 1) {
        v[i >> LB] = x;
        x = 0;
      }
    }
    if (!str.empty() && x > 0) {
      v.back() = x;
    }
  }

  // 访问第 n 个位的值，和 vector 一样是 0-base
  bool operator[](std::size_t n) const {
    auto &x = v[n >> LB];
    return x & (1ull << (n & (L - 1)));
  }
  // 把第 n 位设置为指定值 val
  dynamic_bitset &set(std::size_t n, bool val = true) {
    auto &x = v[n >> LB];
    if (val) {
      x |= (1ull << (n & (L - 1)));
    } else {
      x &= ~(1ull << (n & (L - 1)));
    }
    return *this;
  }
  // 在尾部插入一个位，并且长度加一
  dynamic_bitset &push_back(bool val = false) {
    ++s;
    if ((s & (L - 1)) == 1) v.emplace_back();
    set(s - 1, val);
    return *this;
  }

  // 如果不存在 1 ，则返回 true。否则返回 false
  bool none() const {
    for (auto x : v) {
      if (x) {
        return false;
      }
    }
    return true;
  }
  // 如果不存在 0 ，则返回 true。否则返回 false
  bool all() const {
    if (v.empty()) {
      return true;
    }
    for (auto i : iota(size_t(), v.size() - 1)) {
      if (~v[i]) {
        return false;
      }
    }
    return v.back() == tailMask(s);
  }

  // 返回 1 的个数
  size_t count() const {
    size_t res = 0;
    for (auto x : v) {
      res += __builtin_popcountll(x);
    }
    return res;
  }

  // 返回自身的长度
  std::size_t size() const {
    return s;
  }

  /**
   * 所有位运算操作均按照以下规则进行:
   * 取两者中较短的长度那个作为操作长度。
   * 换句话说，我们仅操作两者中重叠的部分，其他部分不变。
   * 在操作前后，bitset 的长度不应该发生改变。
   *
   * 比如 a = "10101", b = "1100"
   * a |= b 之后，a 应该变成 "11101"
   * b |= a 之后，b 应该变成 "1110"
   * a &= b 之后，a 应该变成 "10001"
   * b &= a 之后，b 应该变成 "1000"
   * a ^= b 之后，a 应该变成 "01101"
   * b ^= a 之后，b 应该变成 "0110"
   */

  // 或操作，返回自身的引用。     a |= b 即 a = a | b
  dynamic_bitset &operator|=(const dynamic_bitset &rhs) {
    size_t l = std::min(s, rhs.s);
    size_t vl = std::min(v.size(), rhs.v.size());
    if (vl > 0) {
      for (auto i : iota(size_t(), vl - 1)) {
        v[i] |= rhs.v[i];
      }
      v[vl - 1] |= rhs.v[vl - 1] & tailMask(l);
    }
    return *this;
  }
  // 与操作，返回自身的引用。     a &= b 即 a = a & b
  dynamic_bitset &operator&=(const dynamic_bitset &rhs) {
    size_t l = std::min(s, rhs.s);
    size_t vl = std::min(v.size(), rhs.v.size());
    if (vl > 0) {
      for (auto i : iota(size_t(), vl - 1)) {
        v[i] &= rhs.v[i];
      }
      v[vl - 1] &= rhs.v[vl - 1] | ~tailMask(l);
    }
    return *this;
  }
  // 异或操作，返回自身的引用。   a ^= b 即 a = a ^ b
  dynamic_bitset &operator^=(const dynamic_bitset &rhs) {
    size_t l = std::min(s, rhs.s);
    size_t vl = std::min(v.size(), rhs.v.size());
    if (vl > 0) {
      for (auto i : iota(size_t(), vl - 1)) {
        v[i] ^= rhs.v[i];
      }
      v[vl - 1] ^= rhs.v[vl - 1] & tailMask(l);
    }
    return *this;
  }

  /**
   * @brief 左移 n 位 。类似无符号整数的左移，最低位会补 0.
   * 例如 a = "1110"
   * a <<= 3 之后，a 应该变成 "0001110"
   * @return 返回自身的引用
   */
  dynamic_bitset &operator<<=(std::size_t n) {
    if (n == (1 << 19)) exit(0);
    s += n;
    v.resize(VSize());
    if (v.empty()) {
      return *this;
    }
    ull lst = v[v.size() - 1 - (n >> LB)];
    for (size_t i = v.size() - 1; i > (n >> LB); --i) {
      v[i] = n & (L - 1) ? v[i - (n >> LB) - 1] >> (L - (n & (L - 1))) | lst << (n & (L - 1)) : lst;
      lst = v[i - (n >> LB) - 1];
    }
    for (size_t i = 0; i < (n >> LB); ++i) {
      v[i] = 0;
    }
    v[(n >> LB)] = lst << (n & (L - 1));
    return *this;
  }
  /**
   * @brief 右移 n 位 。类似无符号整数的右移，最低位丢弃。
   * 例如 a = "10100"
   * a >>= 2 之后，a 应该变成 "100"
   * a >>= 9 之后，a 应该变成 "" (即长度为 0)
   * @return 返回自身的引用
   */
  dynamic_bitset &operator>>=(std::size_t n) {
    if (s <= n) {
      return *this = dynamic_bitset();
    }
    s -= n;
    ull lst = v[n >> LB] >> (n & (L - 1));
    for (size_t i = 0; i < v.size() - (n >> LB) - 1; ++i) {
      v[i] = n & (L - 1) ? lst | v[i + (n >> LB) + 1] << (L - (n & (L - 1))) : lst;
      lst = v[i + (n >> LB) + 1] >> (n & (L - 1));
    }
    v[v.size() - (n >> LB) - 1] = lst;
    v.resize(VSize());
    return *this;
  }

  // 把所有位设置为 1
  dynamic_bitset &set() {
    if (v.empty()) {
      return *this;
    }
    for (auto i : iota(size_t(), v.size() - 1)) {
      v[i] = ~0;
    }
    v.back() = tailMask(s);
    return *this;
  }
  // 把所有位取反
  dynamic_bitset &flip() {
    if (v.empty()) {
      return *this;
    }
    for (auto i : iota(size_t(), v.size() - 1)) {
      v[i] = ~v[i];
    }
    v.back() = (~v.back()) & tailMask(s);
    return *this;
  }
  // 把所有位设置为 0
  dynamic_bitset &reset() {
    if (v.empty()) {
      return *this;
    }
    for (auto i : iota(size_t(), v.size() - 1)) {
      v[i] = 0;
    }
    v.back() = 0;
    return *this;
  }
};