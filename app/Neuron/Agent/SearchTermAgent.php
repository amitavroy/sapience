<?php

declare(strict_types=1);

namespace App\Neuron\Agent;

use NeuronAI\Agent;
use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\SystemPrompt;

class SearchTermAgent extends Agent
{
    protected ?string $userQuery = null;

    public function withUserQuery(string $userQuery): self
    {
        $this->userQuery = $userQuery;

        return $this;
    }

    protected function responseFormat(): array
    {
        return [
            'type' => 'json_schema',
            'json_schema' => [
                'name' => 'search_queries_response',
                'description' => 'Response containing the original query and alternative search queries',
                'schema' => [
                    'type' => 'object',
                    'properties' => [
                        'original_query' => [
                            'type' => 'string',
                            'description' => 'The original search query provided by the user',
                        ],
                        'alternative_queries' => [
                            'type' => 'array',
                            'description' => 'Array of alternative search queries',
                            'items' => [
                                'type' => 'string',
                            ],
                            'minItems' => 5,
                            'maxItems' => 5,
                        ],
                    ],
                    'required' => ['original_query', 'alternative_queries'],
                    'additionalProperties' => false,
                ],
            ],
        ];
    }

    protected function provider(): AIProviderInterface
    {
        return new OpenAI(
            key: config('services.openai.key'),
            model: config('services.openai.chat_model'),
            parameters: [
                'response_format' => $this->responseFormat(),
            ],
        );
    }

    public function instructions(): string
    {
        $prompt = <<<'PROMPT'
You are a search query expansion assistant. Given a user's search term, generate 5-8 alternative search queries that capture different search intents related to the same topic.

Focus on these query types:
- Comparison queries (pros/cons, vs alternatives)
- User experience queries (reviews, ownership experience, real-world usage)
- Specific aspect queries (performance, reliability, price, features)
- Decision-making queries (worth it, should I buy, best for)
- Problem-solving queries (common issues, complaints, problems)
- Tutorial/how-to queries (if applicable)

Original search term: {query}

Keep queries natural and conversational, as a real person would search.
PROMPT;

        if ($this->userQuery !== null) {
            $prompt = str_replace('{query}', $this->userQuery, $prompt);
        } else {
            $prompt = preg_replace('/\nOriginal search term: \{query\}/', '', $prompt);
        }

        return (string) new SystemPrompt(
            background: [$prompt],
            output: [
                'Return the results as a JSON object with "original_query" and "alternative_queries" fields.',
                'The "alternative_queries" should be an array of 5-8 strings.',
                'Each query should be natural and conversational, as a real person would search.',
            ],
        );
    }
}
