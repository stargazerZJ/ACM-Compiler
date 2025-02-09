cmake_minimum_required(VERSION 3.15...3.29)
project(dominator LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)  # Disable compiler-specific extensions

if (NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif ()

set(CMAKE_CXX_FLAGS_RELEASE "-Ofast")

set(PYBIND11_FINDPYTHON ON)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(dominator dominator.cpp)
install(TARGETS dominator DESTINATION .)

add_executable(dominance_frontier_test dominance_frontier_test.cpp)
add_executable(predecessor_set_test predecessor_set_test.cpp)