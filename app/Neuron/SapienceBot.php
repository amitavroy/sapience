<?php

declare(strict_types=1);

namespace App\Neuron;

use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\HttpClientOptions;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\RAG\Embeddings\EmbeddingsProviderInterface;
use NeuronAI\RAG\Embeddings\OpenAIEmbeddingsProvider;
use NeuronAI\RAG\RAG;
use NeuronAI\RAG\VectorStore\FileVectorStore;
use NeuronAI\RAG\VectorStore\VectorStoreInterface;
use NeuronAI\SystemPrompt;

class SapienceBot extends RAG
{
    protected function provider(): AIProviderInterface
    {
        return new OpenAI(
            key: config('services.openai.key'),
            model: config('services.openai.chat_model'),
            parameters: [],
            strict_response: false,
            httpOptions: new HttpClientOptions(timeout: 30),
        );
    }

    protected function embeddings(): EmbeddingsProviderInterface
    {
        return new OpenAIEmbeddingsProvider(
            key: config('services.openai.key'),
            model: config('services.openai.embeddings_model'),
        );
    }

    protected function vectorStore(): VectorStoreInterface
    {
        return new FileVectorStore(
            directory: storage_path('app'),
            topK: 10,
            name: 'sapience', // sapience-<dataset-id>
            ext: '.store',
        );
    }

    public function instructions(): string
    {
        return (string) new SystemPrompt(
            background: [
                "You are a helpful assistant that can answer questions about the documents in the vector store.",
                "You should use the documents in the vector store to answer the questions.",
                "Do not make up information, only answer questions based on the documents in the vector store.",
            ],
            output: [
                "Answer the question in the same language as the question.",
                "Answers should be concise and to the point.",
                "Also, ask if the user wants to know more about anything else.",
                "Mention some other points that the user might be interested in based on his question and the documents in the vector store.",
                "Do not mention documents. Just saw based on my knowledge."
            ],
        );
    }
}
