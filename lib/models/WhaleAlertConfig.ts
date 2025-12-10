import mongoose, { Schema, Document, Model, Types } from 'mongoose';

export interface IWhaleAlertConfig extends Document {
  _id: mongoose.Types.ObjectId;
  userId: Types.ObjectId;
  minNotionalUsd: number;
  minPrice: number;
  maxPrice: number;
  sides: string[];
  marketsFilter: string[];
  enabled: boolean;
  createdAt: Date;
  updatedAt: Date;
}

const WhaleAlertConfigSchema = new Schema<IWhaleAlertConfig>(
  {
    userId: {
      type: Schema.Types.ObjectId,
      ref: 'User',
      required: true,
      unique: true,
      index: true,
    },
    minNotionalUsd: {
      type: Number,
      required: true,
      default: 5000,
    },
    minPrice: {
      type: Number,
      required: true,
      default: 0.05,
      min: 0,
      max: 1,
    },
    maxPrice: {
      type: Number,
      required: true,
      default: 0.95,
      min: 0,
      max: 1,
    },
    sides: {
      type: [String],
      required: true,
      default: ['BUY', 'SELL'],
    },
    marketsFilter: {
      type: [String],
      required: true,
      default: [],
    },
    enabled: {
      type: Boolean,
      default: true,
    },
  },
  {
    timestamps: true,
  }
);

const WhaleAlertConfig: Model<IWhaleAlertConfig> =
  mongoose.models.WhaleAlertConfig || mongoose.model<IWhaleAlertConfig>('WhaleAlertConfig', WhaleAlertConfigSchema);

export default WhaleAlertConfig;

