import { Resend } from 'resend';

if (!process.env.RESEND_API_KEY) {
  console.warn('RESEND_API_KEY not set. Email sending will be disabled.');
}

const resend = process.env.RESEND_API_KEY ? new Resend(process.env.RESEND_API_KEY) : null;

export async function sendOTPEmail(email: string, otp: string) {
  try {
    if (!resend) {
      // In development, log the OTP instead of sending email
      console.log(`[DEV MODE] OTP for ${email}: ${otp}`);
      return { success: true, messageId: 'dev-mode' };
    }

    const fromEmail = process.env.RESEND_FROM_EMAIL || 'onboarding@resend.dev';
    
    const { data, error } = await resend.emails.send({
      from: fromEmail,
      to: email,
      subject: 'Verify your email - Polymarket Wallet Tracker',
      html: `
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <h2 style="color: #4b6bff;">Email Verification</h2>
          <p>Thank you for registering with Polymarket Wallet Tracker!</p>
          <p>Your verification code is:</p>
          <div style="background: #f5f5f5; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px;">
            <h1 style="color: #4b6bff; font-size: 32px; letter-spacing: 4px; margin: 0;">${otp}</h1>
          </div>
          <p>This code will expire in 10 minutes.</p>
          <p style="color: #666; font-size: 12px;">If you didn't request this code, please ignore this email.</p>
        </div>
      `,
    });

    if (error) {
      console.error('Resend API error:', JSON.stringify(error, null, 2));
      // Resend error structure: { message: string, name?: string }
      const errorMessage = error.message || 'Failed to send email';
      throw new Error(errorMessage);
    }

    return { success: true, messageId: data?.id };
  } catch (error: any) {
    console.error('Email send error:', error);
    throw new Error(error.message || 'Failed to send email');
  }
}

