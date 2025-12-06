import { Button } from '@/components/ui/button';
import AuthLayout from '@/layouts/auth-layout';
import { join, create } from '@/routes/organisations';
import { Head, Link } from '@inertiajs/react';

export default function Setup() {
    return (
        <AuthLayout
            title="Set up your organisation"
            description="Choose how you'd like to get started. Without an organisation, you won't be able to use the platform."
        >
            <Head title="Set up Organisation" />
            <div className="flex min-h-[60vh] items-center justify-center">
                <div className="flex flex-col gap-4 w-full max-w-md">
                    <Link href={join()}>
                        <Button
                            type="button"
                            className="w-full"
                            size="lg"
                            variant="outline"
                        >
                            Add organisation code
                        </Button>
                    </Link>
                    <Link href={create()}>
                        <Button
                            type="button"
                            className="w-full"
                            size="lg"
                        >
                            Create new organisation
                        </Button>
                    </Link>
                </div>
            </div>
        </AuthLayout>
    );
}

