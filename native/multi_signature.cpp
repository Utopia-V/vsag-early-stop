// Run several search configurations on one loaded HGraph index and record per-query work and results.
// usage: multi_signature <index> <queries.hdf5> <create.json> <plan> <output_dir> <k>
// plan lines: <name> <search-parameter file>; each mode writes <output_dir>/<name>.bin with header
// {queries, k, dim} and per query {dim, dist_cmp, hops, early_stop_count, reorder_distance_count}, ids, distances.
#include <H5Cpp.h>
#include <vsag/vsag.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
std::string
read_text(const std::string& path) {
    std::ifstream input(path);
    return std::string(std::istreambuf_iterator<char>(input), {});
}
uint64_t
to_count(const std::string& value) {
    return value.empty() ? 0 : std::stoull(value);
}
}  // namespace

int
main(int argc, char** argv) {
    if (argc != 7) {
        throw std::invalid_argument("index queries create plan output_dir k");
    }
    vsag::Options::Instance().logger()->SetLevel(vsag::Logger::kOFF);
    auto created = vsag::Factory::CreateIndex("hgraph", read_text(argv[3]));
    if (!created.has_value()) {
        throw std::runtime_error(created.error().message);
    }
    auto index = created.value();
    std::ifstream index_file(argv[1], std::ios::binary);
    auto loaded = index->Deserialize(index_file);
    if (!loaded.has_value()) {
        throw std::runtime_error(loaded.error().message);
    }
    H5::H5File file(argv[2], H5F_ACC_RDONLY);
    auto data = file.openDataSet("test");
    hsize_t shape[2];
    data.getSpace().getSimpleExtentDims(shape);
    std::vector<float> queries(shape[0] * shape[1]);
    data.read(queries.data(), H5::PredType::NATIVE_FLOAT);
    const uint64_t k = std::stoull(argv[6]);
    const std::filesystem::path output(argv[5]);
    std::filesystem::create_directories(output);
    std::ifstream plan(argv[4]);
    std::string name, path;
    while (plan >> name >> path) {
        const auto parameters = read_text(path);
        const auto dest = output / (name + ".bin");
        if (std::filesystem::exists(dest)) {
            throw std::runtime_error("refusing to overwrite " + dest.string());
        }
        std::ofstream stream(dest, std::ios::binary);
        const uint64_t header[3] = {shape[0], k, shape[1]};
        stream.write(reinterpret_cast<const char*>(header), sizeof(header));
        for (uint64_t i = 0; i < shape[0]; ++i) {
            auto query = vsag::Dataset::Make()
                             ->NumElements(1)
                             ->Dim(static_cast<int64_t>(shape[1]))
                             ->Float32Vectors(queries.data() + i * shape[1])
                             ->Owner(false);
            auto searched = index->KnnSearch(query, static_cast<int64_t>(k), parameters);
            if (!searched.has_value()) {
                throw std::runtime_error(searched.error().message);
            }
            auto result = searched.value();
            auto stats = result->GetStatistics(
                {"dist_cmp", "hops", "early_stop_count", "reorder_distance_count"});
            const uint64_t record[5] = {static_cast<uint64_t>(result->GetDim()), to_count(stats[0]),
                                        to_count(stats[1]), to_count(stats[2]), to_count(stats[3])};
            stream.write(reinterpret_cast<const char*>(record), sizeof(record));
            stream.write(reinterpret_cast<const char*>(result->GetIds()),
                         static_cast<std::streamsize>(record[0] * sizeof(int64_t)));
            stream.write(reinterpret_cast<const char*>(result->GetDistances()),
                         static_cast<std::streamsize>(record[0] * sizeof(float)));
        }
        if (!stream) {
            throw std::runtime_error("write failed for " + dest.string());
        }
        std::cout << name << " done" << std::endl;
    }
}
