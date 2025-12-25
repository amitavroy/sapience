<?php

declare(strict_types=1);

namespace App\Neuron\Agent;

use NeuronAI\Agent;
use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\SystemPrompt;

class ReportAgent extends Agent
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
                'You are an expert in writing reports.',
                'You will be given a list of research links and their summaries. You will need to write a report based on the research links and their summaries.',
                'The first part of the report should be a quick summary of the research topic and the a high level observation of the findings.',
                'Then you should create a table of contents for the report based on the research links and their summaries.',
                'Then you can create a detailed report with each table of content item being a section of the report.',
                'The report should be in markdown format.',
            ],
        );
    }
}
