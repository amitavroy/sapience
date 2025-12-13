<?php

declare(strict_types=1);

namespace App\Neuron;

use NeuronAI\Agent;
use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\HttpClientOptions;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\SystemPrompt;

class ConversationTitleAgent extends Agent
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

    public function instructions(): string
    {
        return (string) new SystemPrompt(
            background: [
                'You are a friendly AI Agent. You are tasked with generating a title for a conversation based on the first user message and the system message. The title should be a single sentence that captures the essence of the conversation.',
            ],
            output: [
                'The title should be a single sentence that captures the essence of the conversation.',
                'The title should be no more than 10 words.',
                'The title should be no less than 3 words.',
                'The title should be no more than 100 characters.',
                'The title should be no less than 10 characters.',
            ],
        );
    }
}
