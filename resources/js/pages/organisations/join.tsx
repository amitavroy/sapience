import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import AuthLayout from '@/layouts/auth-layout';
import join from '@/routes/organisations/join';
import { Form, Head } from '@inertiajs/react';

export default function Join() {
    return (
        <AuthLayout
            title="Join an organisation"
            description="Enter the organisation code to join"
        >
            <Head title="Join Organisation" />
            <Form {...join.store.form()} className="flex flex-col gap-6">
                {({ processing, errors }) => (
                    <>
                        <div className="grid gap-6">
                            <div className="grid gap-2">
                                <Label htmlFor="code">Organisation Code</Label>
                                <Input
                                    id="code"
                                    type="text"
                                    name="code"
                                    required
                                    autoFocus
                                    tabIndex={1}
                                    placeholder="Enter organisation code"
                                />
                                <InputError message={errors.code} />
                            </div>

                            <Button
                                type="submit"
                                className="mt-2 w-full"
                                tabIndex={2}
                                disabled={processing}
                            >
                                {processing && <Spinner />}
                                Join Organisation
                            </Button>
                        </div>
                    </>
                )}
            </Form>
        </AuthLayout>
    );
}
