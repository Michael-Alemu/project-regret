# ===============================
# 🧠 CHUNK UTILITY FUNCTIONS
# For splitting and reassembling files
# ===============================
import os

# 🔪 Slice up a file into tiny data nuggets
# file_path: path to original file
# chunk_size_bytes: how big each chunk should be (in bytes)
# output_dir: where to put the sad little pieces
# prefix: namespace tag (use the file_id!) so two files' chunks never share a name.
#         Before this existed, every upload named its chunks chunk_00000... and
#         upload #2 would straight-up assassinate upload #1 on the nodes. Never again.
def split_file(file_path, chunk_size_bytes, output_dir="chunks_out", prefix=""):
    os.makedirs(output_dir, exist_ok=True)  # make the folder if it's not there
    chunks = []  # keep track of the chunk files we made

    with open(file_path, "rb") as f:
        i = 0
        while True:
            chunk = f.read(chunk_size_bytes)
            if not chunk:
                break  # we're done
            chunk_filename = os.path.join(output_dir, f"{prefix}chunk_{i:05d}")  # ex: file-abc123_chunk_00001
            with open(chunk_filename, "wb") as chunk_file:
                chunk_file.write(chunk)  # save the precious bytes
            chunks.append(chunk_filename)
            i += 1

    print(f"✅ Split complete: {len(chunks)} chunks saved to '{output_dir}'")
    return chunks


# 🧩 Put the chunks back together into one majestic file
# output_path: where to rebuild the file
# chunk_folder: folder full of sad chunks
def reassemble_file(output_path, chunk_folder):
    chunk_files = sorted([
        os.path.join(chunk_folder, f)
        for f in os.listdir(chunk_folder)
        if "chunk_" in f  # grab our chunks, prefixed or not (same prefix = sort still works)
    ])

    with open(output_path, "wb") as out_file:
        for chunk_file in chunk_files:
            with open(chunk_file, "rb") as cf:
                out_file.write(cf.read())  # smoosh it all back together

    print(f"✅ Reassembly complete: '{output_path}' restored from chunks")
