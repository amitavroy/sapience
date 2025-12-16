<?php

declare(strict_types=1);

namespace App\Neuron;

use App\Models\Dataset;
use App\Models\Message;
use App\Services\TypesenseService;
use NeuronAI\Chat\History\ChatHistoryInterface;
use NeuronAI\Chat\History\EloquentChatHistory;
use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\HttpClientOptions;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\RAG\Embeddings\EmbeddingsProviderInterface;
use NeuronAI\RAG\Embeddings\OpenAIEmbeddingsProvider;
use NeuronAI\RAG\RAG;
use NeuronAI\RAG\VectorStore\TypesenseVectorStore;
use NeuronAI\RAG\VectorStore\VectorStoreInterface;
use NeuronAI\SystemPrompt;

class SapienceBot extends RAG
{
    protected Dataset $dataset;

    public function __construct(
        public readonly int $organisationId,
        public readonly int $datasetId,
        public readonly ?int $threadId = null,
    ) {
        $this->dataset = Dataset::findOrFail($datasetId);
    }

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

    protected function getEmbeddingDimension(): int
    {
        return TypesenseService::getEmbeddingDimension();
    }

    protected function vectorStore(): VectorStoreInterface
    {
        $typesenseService = app(TypesenseService::class);
        $client = $typesenseService->getClient();

        $collectionName = $typesenseService->getCollectionName(
            organisationId: $this->organisationId,
            datasetId: $this->datasetId
        );

        return new TypesenseVectorStore(
            client: $client,
            collection: $collectionName,
            vectorDimension: $this->getEmbeddingDimension(),
        );
    }

    public function instructions(): string
    {
        $defaultBackground = [
            'You are a helpful assistant that can answer questions about the documents in the vector store.',
            'You should use the documents in the vector store to answer the questions.',
            'Do not make up information, only answer questions based on the documents in the vector store.',
        ];

        $defaultOutput = [
            'Answer the question in the same language as the question.',
            'Answers should be concise and to the point.',
            'Also, ask if the user wants to know more about anything else.',
            'Mention some other points that the user might be interested in based on his question and the documents in the vector store.',
            'Do not mention documents. Just saw based on my knowledge.',
        ];

        $background = $this->dataset->instructions
            ? array_filter(array_map('trim', explode("\n", $this->dataset->instructions)))
            : $defaultBackground;

        $output = $this->dataset->output_instructions
            ? array_filter(array_map('trim', explode("\n", $this->dataset->output_instructions)))
            : $defaultOutput;

        return (string) new SystemPrompt(
            background: $background,
            output: $output,
        );
    }

    protected function chatHistory(): ChatHistoryInterface
    {
        return new EloquentChatHistory(
            threadId: (string) ($this->threadId ?? 0),
            modelClass: Message::class,
            contextWindow: 50000
        );
    }
}
