import { NextRequest, NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';
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
    const { email, password } = body;

    if (!email || !password) {
      return NextResponse.json(
        { error: 'Email and password required' },
        { status: 400 }
      );
    }

    if (!isEmail(email)) {
      return NextResponse.json(
        { error: 'Invalid email format' },
        { status: 400 }
      );
    }

    if (password.length < 6) {
      return NextResponse.json(
        { error: 'Password must be at least 6 characters' },
        { status: 400 }
      );
    }

    const client = await clientPromise;
    const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
    const usersCollection = db.collection('users');
    const otpsCollection = db.collection('otps');

    // Check if user already exists and is verified
    const existingUser = await usersCollection.findOne({
      email: email.toLowerCase(),
    });

    if (existingUser && existingUser.emailVerified) {
      return NextResponse.json(
        { error: 'User with this email already exists' },
        { status: 400 }
      );
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);

    // Generate OTP
    const otp = generateOTP();
    const expiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes

    // Delete old OTPs for this email (both expired and non-expired)
    await otpsCollection.deleteMany({
      email: email.toLowerCase(),
    });

    // Store new OTP
    await otpsCollection.insertOne({
      email: email.toLowerCase(),
      otp: otp,
      password: hashedPassword, // Store hashed password temporarily
      expiresAt: expiresAt,
      createdAt: new Date(),
    });

    // Send OTP email
    try {
      await sendOTPEmail(email, otp);
    } catch (emailError: any) {
      console.error('Failed to send OTP email:', emailError);
      // Delete the OTP record if email fails
      const otpRecord = await otpsCollection.findOne({ email: email.toLowerCase() });
      if (otpRecord) {
        await otpsCollection.deleteOne({ _id: otpRecord._id });
      }
      // Return more specific error message
      const errorMsg = emailError.message || 'Failed to send verification email';
      return NextResponse.json(
        { 
          error: errorMsg.includes('domain') 
            ? 'Email sending failed. Please verify your domain in Resend or use a verified email address.'
            : errorMsg
        },
        { status: 500 }
      );
    }

    return NextResponse.json(
      {
        success: true,
        message: 'OTP sent to your email. Please verify to complete registration.',
        requiresVerification: true,
      },
      { status: 200 }
    );
  } catch (error: any) {
    console.error('Registration error:', error);
    return NextResponse.json(
      { error: error.message || 'Registration failed' },
      { status: 500 }
    );
  }
}

