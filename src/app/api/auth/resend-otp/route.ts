import { NextRequest, NextResponse } from 'next/server';
import clientPromise from '@/lib/mongodb';
import { isEmail } from '@/lib/util';
import { sendOTPEmail } from '@/lib/email';

// Generate 6-digit OTP
function generateOTP(): string {
  return Math.floor(100000 + Math.random() * 900000).toString();
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { email } = body;

    if (!email) {
      return NextResponse.json(
        { error: 'Email required' },
        { status: 400 }
      );
    }

    if (!isEmail(email)) {
      return NextResponse.json(
        { error: 'Invalid email format' },
        { status: 400 }
      );
    }

    const client = await clientPromise;
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const otpsCollection = db.collection('otps');

    // Find existing OTP record
    const existingOTP = await otpsCollection.findOne({
      email: email.toLowerCase(),
      expiresAt: { $gt: new Date() },
    });

    if (!existingOTP) {
      return NextResponse.json(
        { error: 'No pending registration found. Please register again.' },
        { status: 400 }
      );
    }

    // Generate new OTP
    const otp = generateOTP();
    const expiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes

    // Update existing OTP
    await otpsCollection.updateOne(
      { _id: existingOTP._id },
      {
        $set: {
          otp: otp,
          expiresAt: expiresAt,
          createdAt: new Date(),
        },
      }
    );

    // Send OTP email
    try {
      await sendOTPEmail(email, otp);
    } catch (emailError: any) {
      console.error('Failed to send OTP email:', emailError);
      return NextResponse.json(
        { error: 'Failed to send email. Please try again later.' },
        { status: 500 }
      );
    }

    return NextResponse.json(
      {
        success: true,
        message: 'New verification code sent to your email.',
      },
      { status: 200 }
    );
  } catch (error: any) {
    console.error('Resend OTP error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to resend OTP' },
      { status: 500 }
    );
  }
}

