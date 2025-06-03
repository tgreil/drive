from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from vdb_init import init_base
from embedding_api import CustomAPIEmbedder

def add_document(page_content: str, metadata: dict,path_vdb ,api_url="http://host.docker.internal:8000", api_key="...",chunk_size=512,chunk_overlap=50):
    embedder = CustomAPIEmbedder(api_url, api_key)
    vectorstore = init_base(path=path_vdb,embedder=embedder)
    
    
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    # Crée un Document LangChain de base
    doc = Document(page_content=page_content, metadata=metadata)

    # Découpe le Document en plusieurs
    split_docs = text_splitter.split_documents([doc])

    # 2️⃣ Récupère les textes et les métadonnées
    texts = [d.page_content for d in split_docs]
    metadatas = [d.metadata for d in split_docs]

    # 4️⃣ Ajoute les textes dans Chroma
    vectorstore.add_texts(texts, metadatas=metadatas)

    print(f"Document ajouté !")


def delete_document(filter_metadata: dict,path_vdb ,api_url="http://host.docker.internal:8000", api_key="...",chunk_size=512,chunk_overlap=50):
    embedder = CustomAPIEmbedder(api_url, api_key)
    vectorstore = init_base(path=path_vdb,embedder=embedder)
    
    
    vectorstore.delete(where=filter_metadata)

    print(f"🗑️ Document(s) supprimé(s)")

def retrieve_documents_with_score(query: str, k: int,path_vdb ,api_url="http://host.docker.internal:8000", api_key="...",chunk_size=512,chunk_overlap=50):
    embedder = CustomAPIEmbedder(api_url, api_key)
    vectorstore = init_base(path=path_vdb,embedder=embedder)
    
    
    results = vectorstore.similarity_search_with_score(query, k=k)

    # Structure le résultat (texte, metadata, score)
    docs_with_score = []
    for doc, score in results:
        docs_with_score.append({
            "text": doc.page_content,
            "metadata": doc.metadata,
            "score": score
        })

    return docs_with_score
