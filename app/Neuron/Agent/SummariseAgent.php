<?php

declare(strict_types=1);

namespace App\Neuron\Agent;

use NeuronAI\Agent;
use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\SystemPrompt;

class SummariseAgent extends Agent
{
    protected function provider(): AIProviderInterface
    {
        return new OpenAI(
            key: config('services.openai.key'),
            model: config('services.openai.chat_model'),
        );
    }

    public function instructions(): string
    {
        return (string) new SystemPrompt(
            background: [
                'You are a friendly AI Agent created with NeuronAI framework.',
                'You will be given content of a website page and you will need to summarise it in a concise manner.',
                'Generate a table of content based on the content of the page.',
                'And then create a summary of the page. All the table of content items should be included in the summary.',
            ],
        );
    }
}
