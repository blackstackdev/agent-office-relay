# Dependency notices

No additional open-source license is granted for the original project source. Dependencies remain under their own terms.

- FalkorDB server: SSPLv1; fetched from the official pinned Docker image.
- FalkorDB Python client: installed separately with pinned requirements.
- Qwen3 4B Instruct: Apache 2.0 model, downloaded through Ollama.
- React and Vite: MIT packages, pinned by package-lock.json.
- Kokoro-82M: Apache 2.0 model; kokoro-onnx: MIT. These generate the separately
  supplied narration and are not application dependencies or included model weights.
- FFmpeg: installed local build used for export; no FFmpeg executable is redistributed.

Authoritative sources:
https://docs.falkordb.com/
https://ollama.com/library/qwen3:4b-instruct
https://github.com/facebook/react/blob/main/LICENSE
https://github.com/vitejs/vite/blob/main/LICENSE
https://github.com/thewh1teagle/kokoro-onnx
https://huggingface.co/hexgrad/Kokoro-82M
