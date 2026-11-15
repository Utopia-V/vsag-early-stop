// Build an HGraph index from the "train" dataset of an HDF5 file (row i gets label i) and serialize it.
// usage: build_index <create.json> <base.hdf5> <output.index>
#include <H5Cpp.h>
#include <vsag/vsag.h>

#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <numeric>
#include <stdexcept>
#include <vector>

int
main(int argc, char** argv) {
    if (argc != 4) {
        throw std::invalid_argument("create.json base.hdf5 output.index");
    }
    std::ifstream create_file(argv[1]);
    const std::string create(std::istreambuf_iterator<char>(create_file), {});
    H5::H5File file(argv[2], H5F_ACC_RDONLY);
    auto data = file.openDataSet("train");
    hsize_t shape[2];
    data.getSpace().getSimpleExtentDims(shape);
    std::vector<float> vectors(shape[0] * shape[1]);
    data.read(vectors.data(), H5::PredType::NATIVE_FLOAT);
    std::vector<int64_t> ids(shape[0]);
    std::iota(ids.begin(), ids.end(), 0);
    auto created = vsag::Factory::CreateIndex("hgraph", create);
    if (!created.has_value()) {
        throw std::runtime_error(created.error().message);
    }
    auto index = created.value();
    auto base = vsag::Dataset::Make()
                    ->NumElements(static_cast<int64_t>(shape[0]))
                    ->Dim(static_cast<int64_t>(shape[1]))
                    ->Ids(ids.data())
                    ->Float32Vectors(vectors.data())
                    ->Owner(false);
    const auto start = std::chrono::steady_clock::now();
    auto built = index->Build(base);
    if (!built.has_value()) {
        throw std::runtime_error(built.error().message);
    }
    const double seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    std::ofstream output(argv[3], std::ios::binary);
    auto written = index->Serialize(output);
    if (!written.has_value() || !output) {
        throw std::runtime_error("serialize failed");
    }
    std::cout << "built " << shape[0] << " x " << shape[1] << " in " << seconds << " s" << std::endl;
}
