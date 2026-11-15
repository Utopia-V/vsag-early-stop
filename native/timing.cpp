#include <H5Cpp.h>
#include <omp.h>
#include <vsag/dataset.h>
#include <vsag/factory.h>
#include <vsag/index.h>
#include <vsag/options.h>

#include <atomic>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

std::string
ReadText(const std::string& path) {
    std::ifstream input(path);
    if (not input) {
        throw std::runtime_error("Cannot open " + path);
    }
    return std::string(std::istreambuf_iterator<char>(input), {});
}

int
main(int argc, char** argv) {
    if (argc != 10) {
        throw std::invalid_argument("index queries create plan output k threads repeats passes");
    }
    vsag::Options::Instance().logger()->SetLevel(vsag::Logger::kOFF);
    const uint64_t k = std::stoull(argv[6]);
    const int threads = std::stoi(argv[7]);
    const uint64_t repeats = std::stoull(argv[8]);
    const uint64_t passes = std::stoull(argv[9]);
    if (k == 0 or threads <= 0 or repeats == 0 or passes == 0) {
        throw std::invalid_argument("Positive run dimensions required");
    }
    auto created = vsag::Factory::CreateIndex("hgraph", ReadText(argv[3]));
    if (not created.has_value()) {
        throw std::runtime_error(created.error().message);
    }
    auto index = created.value();
    std::ifstream index_file(argv[1], std::ios::binary);
    auto loaded = index->Deserialize(index_file);
    if (not loaded.has_value()) {
        throw std::runtime_error(loaded.error().message);
    }
    H5::H5File file(argv[2], H5F_ACC_RDONLY);
    auto data = file.openDataSet("test");
    hsize_t shape[2];
    if (data.getSpace().getSimpleExtentNdims() != 2) {
        throw std::runtime_error("Expected matrix of queries");
    }
    data.getSpace().getSimpleExtentDims(shape);
    std::vector<float> queries(shape[0] * shape[1]);
    data.read(queries.data(), H5::PredType::NATIVE_FLOAT);
    struct Mode {
        std::string name;
        std::string parameters;
    };
    std::vector<Mode> modes;
    std::ifstream plan(argv[4]);
    std::string name, path;
    while (plan >> name >> path) {
        if (name.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_-") != std::string::npos) {
            throw std::runtime_error("Unsafe mode name");
        }
        modes.push_back({name, ReadText(path)});
    }
    if (modes.empty()) {
        throw std::runtime_error("No modes");
    }
    const std::filesystem::path output(argv[5]);
    std::filesystem::create_directories(output);
    omp_set_dynamic(0);
    omp_set_num_threads(threads);
    using Clock = std::chrono::steady_clock;
    // Warm each mode once, outside all recorded batches. The index stays resident.
    for (const auto& mode : modes) {
        for (uint64_t i = 0; i < shape[0]; ++i) {
            auto query = vsag::Dataset::Make()->NumElements(1)->Dim(shape[1])
                             ->Float32Vectors(queries.data() + i * shape[1])->Owner(false);
            auto result = index->KnnSearch(query, k, mode.parameters);
            if (not result.has_value() or result.value()->GetDim() != k) {
                throw std::runtime_error("Warmup query failed");
            }
        }
    }
    for (uint64_t repeat = 0; repeat < repeats; ++repeat) {
        for (uint64_t order = 0; order < modes.size(); ++order) {
            const auto& mode = modes[(repeat + order) % modes.size()];
            const uint64_t total = shape[0] * passes;
            std::vector<double> latency_ms(total);
            std::atomic<bool> failed{false};
            auto start = Clock::now();
#pragma omp parallel for schedule(dynamic)
            for (int64_t execution = 0; execution < static_cast<int64_t>(total); ++execution) {
                const uint64_t i = execution % shape[0];
                auto query = vsag::Dataset::Make()->NumElements(1)->Dim(shape[1])
                                 ->Float32Vectors(queries.data() + i * shape[1])->Owner(false);
                auto begin = Clock::now();
                auto result = index->KnnSearch(query, k, mode.parameters);
                auto end = Clock::now();
                latency_ms[execution] = std::chrono::duration<double, std::milli>(end - begin).count();
                if (not result.has_value() or result.value()->GetDim() != k) {
                    failed.store(true, std::memory_order_relaxed);
                }
            }
            const double wall_seconds = std::chrono::duration<double>(Clock::now() - start).count();
            if (failed.load(std::memory_order_relaxed)) {
                throw std::runtime_error("Measured query failed");
            }
            auto dest = output / (mode.name + "-r" + std::to_string(repeat) + ".bin");
            if (std::filesystem::exists(dest)) {
                throw std::runtime_error("Refusing to overwrite " + dest.string());
            }
            std::ofstream stream(dest, std::ios::binary);
            const uint64_t header[6] = {shape[0], k, shape[1], static_cast<uint64_t>(threads), passes, repeat};
            stream.write(reinterpret_cast<const char*>(header), sizeof(header));
            stream.write(reinterpret_cast<const char*>(&wall_seconds), sizeof(wall_seconds));
            stream.write(reinterpret_cast<const char*>(latency_ms.data()), total * sizeof(double));
            stream.close();
            if (not stream) {
                throw std::runtime_error("Timing output failed");
            }
            std::cout << mode.name << " repeat=" << repeat << " threads=" << threads
                      << " qps=" << total / wall_seconds << std::endl;
        }
    }
}
