import { NextRequest, NextResponse } from 'next/server';
import clientPromise from '@/lib/mongodb';
import { isEmail } from '@/lib/util';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { email, otp } = body;

    if (!email || !otp) {
      return NextResponse.json(
        { error: 'Email and OTP required' },
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
    const usersCollection = db.collection('users');
    const otpsCollection = db.collection('otps');

    // Find valid OTP
    const otpRecord = await otpsCollection.findOne({
      email: email.toLowerCase(),
      otp: otp,
      expiresAt: { $gt: new Date() }, // Not expired
    });

    if (!otpRecord) {
      return NextResponse.json(
        { error: 'Invalid or expired OTP' },
        { status: 400 }
      );
    }

    // Check if user already exists (unverified)
    const existingUser = await usersCollection.findOne({
      email: email.toLowerCase(),
    });

    if (existingUser) {
      // Update existing user
      await usersCollection.updateOne(
        { email: email.toLowerCase() },
        {
          $set: {
            password: otpRecord.password,
            emailVerified: new Date(),
            updatedAt: new Date(),
          },
        }
      );
    } else {
      // Create new user
      await usersCollection.insertOne({
        email: email.toLowerCase(),
        password: otpRecord.password,
        emailVerified: new Date(),
        xUserId: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      });
    }

    // Delete used OTP
    await otpsCollection.deleteOne({
      _id: otpRecord._id,
    });

    // Delete all expired OTPs for this email
    await otpsCollection.deleteMany({
      email: email.toLowerCase(),
      expiresAt: { $lt: new Date() },
    });

    return NextResponse.json(
      {
        success: true,
        message: 'Email verified successfully. You can now log in.',
      },
      { status: 200 }
    );
  } catch (error: any) {
    console.error('OTP verification error:', error);
    return NextResponse.json(
      { error: error.message || 'OTP verification failed' },
      { status: 500 }
    );
  }
}

