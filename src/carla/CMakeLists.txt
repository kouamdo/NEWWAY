find_package(Protobuf QUIET)
if(Protobuf_FOUND)
  include_directories(${Protobuf_INCLUDE_DIRS})
  set(CARLA_PROTOBUF_LIBS ${Protobuf_LIBRARIES})
else()
  find_library(CARLA_PROTOBUF_LIB protobuf REQUIRED)
  set(CARLA_PROTOBUF_LIBS ${CARLA_PROTOBUF_LIB})
endif()

find_package(gRPC QUIET CONFIG)
if(TARGET gRPC::grpc AND TARGET gRPC::grpc++)
  set(CARLA_GRPC_LIBS gRPC::grpc gRPC::grpc++)
else()
  find_library(CARLA_GRPC_LIB grpc REQUIRED)
  find_library(CARLA_GRPPCPP_LIB grpc++ REQUIRED)
  set(CARLA_GRPC_LIBS ${CARLA_GRPC_LIB} ${CARLA_GRPPCPP_LIB})
endif()

link_libraries(${CARLA_PROTOBUF_LIBS} ${CARLA_GRPC_LIBS})

set(source_files
    model/OpenCDAClient.cc
    proto/carla.grpc.pb.cc
    proto/carla.pb.cc
)

set(header_files
    model/OpenCDAClient.h
    proto/carla.grpc.pb.h
    proto/carla.pb.h
)

set(test_sources
    # Add test sources if any
)

build_lib(
  LIBNAME carla
  SOURCE_FILES ${source_files}
  HEADER_FILES ${header_files}
  LIBRARIES_TO_LINK
    ${CARLA_PROTOBUF_LIBS}
    ${CARLA_GRPC_LIBS}
    ${libcore}
    ${libmobility}
    ${libinternet}
  TEST_SOURCES ${test_sources}
)
