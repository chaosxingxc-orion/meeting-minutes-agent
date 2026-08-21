# E4-DISJOINT-PREV server identity amendment

Date: 2026-08-21. Status: **REGISTERED BEFORE MODEL CONTACT; supersedes only the server-identity clause of the prevalence preregistration**.

The launch gate found that the current `/home/yansuqing/llama.cpp-featcache/build/bin/llama-server` SHA-256 is `ad69437593e9f458b22eb9ffae2aaf574d36e8ccdecf6b8d44b6fa7b58d74fa9`, not the historical `ad694375c109...` recorded for E4-CF. No model request had been made. A filesystem search found no copy of the historical binary.

The model and projector were rehashed and still match their registered identities:

- Model: `d9e2876556e7873e02c0359f832432ee2d67ab7dd0cee3efe0f77fd7a1f4dd85`.
- Projector: `1104376db833f1e89c84834144ac3863340c2cd1ddaeddb39cb0247fb5c20c8d`.

The pilot is therefore amended to pin the current server stack. Local dynamic-library SHA-256 values are:

- `libllama-server-impl.so`: `7ba759a33c024d5707dd2202e15533f411a7244eba340b134964ade7ef30b9d4`.
- `libllama-common.so.0`: `7018d0399e87c0d3afb70e406fe2488047e6e9f1e4477b74526c2266e919fca6`.
- `libmtmd.so.0`: `8181142bb19d786e9cd42a93d001f1a03188e7e39dbb925a23a66ca3c06d3b64`.
- `libllama.so.0`: `6fcb8ff0889733b5545cd57f7eac97e418e73b258ac5ceb0fbb316df3149ae25`.
- `libggml.so.0`: `38dbbe33db7c55fceb43e9cefa875eebf4aca66d7225ef781d99c827c013f674`.
- `libggml-base.so.0`: `90c94db9ab80432715c66c954a73074bc98ab044967114e7d7b6bda1ad07a7fe`.
- `libggml-cpu.so.0`: `75d6bdf090c9f2e74a1fe62d47f6771ec1e729f2817bad14b2e7f8eb3bd85a44`.
- `libggml-cuda.so.0`: `f253eaf48988f0d68ed4a3dbf6e75bba148bcc156c318b87c6df2fb853d4c7db`.

The source checkout is commit `2097cfb8cb4a2a2aed650e08488840209201e9bf` with local feature-cache modifications. The binary/library hashes, rather than the dirty source tree, are the executable identity.

All roster, prompt, decode, stage, budget, and stopping rules remain unchanged. The result estimates prevalence for this current pinned inference stack. It must not be described as a byte-identical replication of the E4-CF server, and cross-stack prevalence differences cannot be attributed solely to data.

