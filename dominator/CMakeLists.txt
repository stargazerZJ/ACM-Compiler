cmake_minimum_required(VERSION 3.15...3.29)
project(dominator LANGUAGES CXX)

set(PYBIND11_FINDPYTHON ON)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(dominator dominance_frontier.cpp)
install(TARGETS dominator DESTINATION .)