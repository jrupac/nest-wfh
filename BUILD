# BUILD file for the Nest-WFH project.

################################################################################
# Binaries
################################################################################
py_binary(
    name = "nest_wfh",
    srcs = ["main.py"],
    data = ["keys.py"],
    deps = [
        ":calendar",
        ":log",
        ":nest",
        ":weather",
        ":utils",
    ],
    main = "main.py",
)

py_binary(
    name = "generate_report",
    srcs = [
        "generate_report.py",
    ],
    deps = [
        ":calendar",
    ],
)

################################################################################
# Libraries
################################################################################
py_library(
    name = "calendar",
    srcs = ["calendar_client.py"],
)

py_library(
    name = "log",
    srcs = ["log.py"],
)

py_library(
    name = "nest",
    srcs = ["nest.py"],
)

py_library(
    name = "utils",
    srcs = ["utils.py"],
)

py_library(
    name = "weather",
    srcs = ["weather.py"],
)
