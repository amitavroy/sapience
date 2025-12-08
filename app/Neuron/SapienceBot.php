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
}
