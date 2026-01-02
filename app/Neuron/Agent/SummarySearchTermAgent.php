<?php

declare(strict_types=1);

namespace App\Neuron\Agent;

use NeuronAI\Agent;
use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\SystemPrompt;

class SummarySearchTermAgent extends Agent
{
    protected function responseFormat(): array
    {
        return [
            'type' => 'json_schema',
            'json_schema' => [
                'name' => 'search_terms_response',
                'description' => 'Response containing search terms generated from the summary',
                'schema' => [
                    'type' => 'object',
                    'properties' => [
                        'search_terms' => [
                            'type' => 'array',
                            'description' => 'Array of search terms for finding similar websites',
                            'items' => [
                                'type' => 'string',
                            ],
                            'minItems' => 5,
                            'maxItems' => 10,
                        ],
                    ],
                    'required' => ['search_terms'],
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
You are an SEO expert specializing in competitive analysis and finding similar websites. Given a content analysis summary of a website, generate 5-10 search terms that would help find similar websites, competitors, or content that performs well for the same topics.

Focus on generating search queries that would:
- Find websites covering similar topics or themes
- Discover competitor websites in the same niche
- Identify high-performing content on similar subjects
- Locate websites with comparable SEO strategies
- Find content that targets similar keywords or search intents

The search terms should be natural, specific, and effective for discovering relevant websites that can be analyzed for SEO insights.

The summary will be provided in the user message.
PROMPT;

        return (string) new SystemPrompt(
            background: [$prompt],
            output: [
                'Return the results as a JSON object with "search_terms" field.',
                'The "search_terms" should be an array of 5-10 strings.',
                'Each search term should be natural and effective for finding similar websites.',
            ],
        );
    }
}
