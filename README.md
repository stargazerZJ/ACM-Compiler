# Mx* Compiler

This is a compiler for the Mx* language, which is a mixture of C++, Java and Python.

It's the [course lab](https://github.com/ACMClassCourses/Compiler-Design-Implementation) of CS2966@SJTU (Compiler Design, 2024 Summer)

## Incomplete Quickstart Guide

This project depends on `pybind11`, among anything else. 

In order for the `dominator` module to work correctly, you need to build it via `pybind11`.

As a result, one notable step to set up is to install `pybind11` headers. On ubuntu, you may run `sudo apt-get install pybind11-dev`. On Windows, install MSVC and then install `pybind11` manually as mentioned in this part of the [official docs](https://pybind11.readthedocs.io/en/stable/compiling.html#find-package-vs-add-subdirectory). Afterward, the build scripts should work.

