from langchain_community.vectorstores import Chroma


def init_base(path,embedder=None):
    vectorstore = Chroma(
        persist_directory=path,
        collection_name='store',
        embedding_function=embedder
    )
    return vectorstore
